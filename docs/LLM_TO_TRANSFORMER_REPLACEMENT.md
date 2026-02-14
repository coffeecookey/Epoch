# Replacing LLM with Transformers in NutriTwin

This document describes how the NutriTwin LLM system (currently Gemini-based) can be replaced with local transformer models: sentence-transformers for semantic similarity, zero-shot classifiers for ingredient risk, and Flan-T5 for explanations. It also explains how each model can be trained or fine-tuned for better performance.

---

## Current LLM Usage in NutriTwin

| Component | Current Implementation | Purpose |
|-----------|------------------------|---------|
| **LLMSwapAgent** | Gemini (Google API) | Agentic swap discovery: identifies risky ingredients, calls FlavorDB/RecipeDB, selects substitutes |
| **IngredientAnalyzer** | Rule-based (keyword + nutrition) | Identifies unhealthy ingredients (trans fats, high sugar, etc.) |
| **SwapEngine** | Rule-based (FlavorDB + heuristics) | Ranks substitutes by flavor match + health improvement |
| **LLMExplainer** | Template-based (no real LLM) | Generates natural language explanations for scores and swaps |

---

## Replacement Architecture

| LLM/Logic | Transformer Replacement | Integration Point |
|-----------|-------------------------|-------------------|
| SwapEngine ranking | `all-MiniLM-L6-v2` | Semantic similarity for substitute ordering |
| IngredientAnalyzer | `bart-large-mnli` / `deberta-v3-base-zeroshot` | Zero-shot "is this risky?" classification |
| LLMExplainer | `flan-t5-small` | One-sentence explanations from structured input |

---

## 1. Sentence-Transformers: `all-MiniLM-L6-v2`

### Purpose
**Rank substitute options by semantic similarity** to the original ingredient. Improves over simple string/flavor matching by understanding that "butter" and "margarine" are conceptually similar, even if molecule overlap is different.

### Install
```bash
pip install sentence-transformers
```

### Usage
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

original = "butter"
candidates = ["olive oil", "coconut oil", "margarine", "ghee", "avocado"]

# Encode original and candidates
orig_emb = model.encode(original)
cand_embs = model.encode(candidates)

# Cosine similarity
from sklearn.metrics.pairwise import cosine_similarity
scores = cosine_similarity([orig_emb], cand_embs)[0]

# Rank by similarity
ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
# e.g. [("ghee", 0.72), ("margarine", 0.68), ("coconut oil", 0.55), ...]
```

### Integration in SwapEngine
- After `SwapEngine.find_substitutes()` returns candidates, re-rank them using semantic similarity to the original ingredient.
- Combine: `final_score = 0.6 * flavor_match + 0.3 * health_improvement + 0.1 * semantic_similarity` (or tune weights).

### Model Size & Performance
- ~80 MB, runs on CPU
- ~22M parameters, 384-dim embeddings

### How to Train / Fine-Tune

**Option A: Fine-tune on ingredient pairs**
```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Triplet: (anchor, positive, negative)
# e.g. (original, good_substitute, bad_substitute)
train_examples = [
    InputExample(texts=["butter", "olive oil", "soy sauce"]),
    InputExample(texts=["white sugar", "honey", "salt"]),
    # ... more from FlavorDB/RecipeDB or human annotations
]

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
train_loss = losses.TripletLoss(model)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=100,
    output_path="./models/ingredient-similarity-v1",
)
```

**Option B: Contrastive learning**
- Use `MultipleNegativesRankingLoss` with (query, positive) pairs.
- Data: `(original_ingredient, accepted_substitute)` from user feedback or recipe pairs.

---

## 2. Zero-Shot Classification: `bart-large-mnli` / `deberta-v3-base-zeroshot-v2.0`

### Purpose
**Zero-shot "is this ingredient risky?"** or **"What category?"** without training. Replaces keyword-based logic in `IngredientAnalyzer` with a model that can classify ingredients into labels like `["healthy", "unhealthy", "high_sodium", "refined", "high_sugar", "trans_fat"]`.

### Install
```bash
pip install transformers torch
```

### Usage
```python
from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",  # or "facebook/bart-large-mnli"
)

ingredient = "refined white sugar"
labels = ["healthy", "unhealthy", "high_sodium", "refined_sugar", "trans_fat", "whole_food"]

result = classifier(ingredient, labels, multi_label=True)
# result["labels"] = ["refined_sugar", "unhealthy", ...]
# result["scores"] = [0.89, 0.72, ...]
```

### Integration in IngredientAnalyzer
- Replace `UNHEALTHY_KEYWORDS` matching with zero-shot classification.
- Ingredients with high scores for `unhealthy`, `refined_sugar`, `trans_fat`, etc. become `RiskyIngredient` instances.
- Map labels to priority (e.g. `trans_fat` → 5, `refined_sugar` → 4).

### Model Comparison

| Model | Size | Speed | Multi-label | Notes |
|-------|------|-------|-------------|-------|
| `facebook/bart-large-mnli` | ~1.6 GB | Slower | No (single) | Strong NLI, good for binary/ternary |
| `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` | ~440 MB | Faster | Yes | Optimized for zero-shot, multi-label |

### How to Train / Fine-Tune

**Option A: Fine-tune DeBERTa for ingredient classification**
```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments
from datasets import Dataset

model_name = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=len(LABELS))

# Your labeled data: (ingredient, label)
# e.g. [("butter", "unhealthy"), ("broccoli", "healthy"), ...]
train_data = Dataset.from_dict({"text": [...], "label": [...]})

def tokenize(examples):
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=128)

train_data = train_data.map(tokenize, batched=True)

training_args = TrainingArguments(
    output_dir="./models/ingredient-classifier",
    num_train_epochs=3,
    per_device_train_batch_size=16,
    learning_rate=2e-5,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_data,
)
trainer.train()
trainer.save_model("./models/ingredient-classifier")
```

**Option B: Few-shot / prompt-based**
- Use the same model in zero-shot mode with more specific labels.
- No training; improve by curating better label sets.

---

## 3. Text Generation: `google/flan-t5-small` (Optional)

### Purpose
**One-sentence explanation** from structured input: e.g. `"Score: 72. Swap: butter → olive oil. Improve: 8."` → `"Swapping butter for olive oil improves heart health by reducing saturated fat."`

### Install
```bash
pip install transformers torch
```

### Usage
```python
from transformers import T5ForConditionalGeneration, T5Tokenizer

model_name = "google/flan-t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

input_text = (
    "Summarize in one sentence: Health score 72. Swap butter for olive oil. "
    "Score improvement: 8 points. Reason: reduces saturated fat."
)
inputs = tokenizer(input_text, return_tensors="pt", max_length=256, truncation=True)
outputs = model.generate(**inputs, max_new_tokens=50)
explanation = tokenizer.decode(outputs[0], skip_special_tokens=True)
```

### Integration in LLMExplainer
- Replace `_template_swap_explanation()` with a call to Flan-T5.
- Input: structured string (score, swaps, improvement).
- Output: natural language explanation.

### Organizer Clarification
- **Flan-T5** is a **encoder-decoder transformer**, not a large language model (LLM).
- LLMs are typically 7B+ parameters, autoregressive, and general-purpose. Flan-T5-small is ~80M params and task-finetuned.
- Confirm with the organizer that Flan-T5 counts as "transformer" and not "LLM" for competition rules.

### How to Train / Fine-Tune

**Option A: Fine-tune for explanation generation**
```python
from transformers import T5ForConditionalGeneration, T5Tokenizer, Seq2SeqTrainer, Seq2SeqTrainingArguments
from datasets import Dataset

model_name = "google/flan-t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

# Data: (input, target)
# input: "Score: 72. Swap: butter → olive oil. Improve: 8."
# target: "Swapping butter for olive oil reduces saturated fat and improves heart health."
train_data = Dataset.from_dict({
    "input": ["Score: 72. Swap: butter → olive oil. Improve: 8.", ...],
    "target": ["Swapping butter for olive oil reduces saturated fat.", ...],
})

def preprocess(examples):
    model_inputs = tokenizer(
        examples["input"],
        max_length=128,
        truncation=True,
    )
    labels = tokenizer(
        examples["target"],
        max_length=64,
        truncation=True,
    )
    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

train_data = train_data.map(preprocess, batched=True, remove_columns=["input", "target"])

training_args = Seq2SeqTrainingArguments(
    output_dir="./models/swap-explainer",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    learning_rate=5e-5,
    predict_with_generate=True,
)

trainer = Seq2SeqTrainer(
    model=model,
    args=training_args,
    train_dataset=train_data,
)
trainer.train()
trainer.save_model("./models/swap-explainer")
```

**Option B: Larger variants**
- `google/flan-t5-base` (~250M): better quality, more compute.
- `google/flan-t5-large` (~780M): best quality, needs GPU.

---

## Summary: Replacement Checklist

| Step | Action |
|------|--------|
| 1 | Add `sentence-transformers`; use `all-MiniLM-L6-v2` to re-rank SwapEngine candidates by semantic similarity |
| 2 | Add `transformers` + `torch`; use zero-shot pipeline (DeBERTa or BART) to classify ingredients in IngredientAnalyzer |
| 3 | (Optional) Add Flan-T5 for LLMExplainer; generate explanations from structured swap data |
| 4 | Disable `LLMSwapAgent` (Gemini) in config; keep rule-based SwapEngine + FlavorDB as backbone |

---

## Requirements Summary

```
# requirements-transformer.txt
sentence-transformers>=2.2.0
transformers>=4.30.0
torch>=2.0.0
scikit-learn>=1.0.0   # for cosine_similarity
```

---

## Training Data Sources

| Model | Data Source |
|-------|-------------|
| **all-MiniLM-L6-v2** | FlavorDB similar-ingredient pairs; user-accepted swaps; RecipeDB co-occurrence |
| **Zero-shot classifier** | Manually labeled ingredients (healthy/unhealthy/category); UNHEALTHY_KEYWORDS as weak labels |
| **Flan-T5** | Template-generated (input, target) pairs; optionally human-edited explanations |

---

## Estimated Resource Usage

| Model | RAM (approx) | GPU (optional) | First-load time |
|-------|--------------|----------------|-----------------|
| all-MiniLM-L6-v2 | ~500 MB | No | ~5 s |
| deberta-v3-base-zeroshot | ~1.5 GB | Yes (recommended) | ~10 s |
| flan-t5-small | ~500 MB | Yes (recommended) | ~8 s |

All models can run on CPU; GPU accelerates inference 5–10×.
