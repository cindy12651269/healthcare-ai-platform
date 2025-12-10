# Healthcare AI — Retrieval Knowledge Base

This document provides structured medical knowledge for improving clinical-style reasoning, symptom interpretation, and summary generation within the Healthcare AI Platform.
The content is non-diagnostic and focuses on **general patterns**, **risk indicators**, and **patient-friendly explanations** suitable for LLM retrieval grounding.

---

## 1. Common Symptoms and Associated Context

### Chest Pain

Chest pain can originate from non-cardiac or cardiac sources.
Important details to consider:

* Onset: sudden vs gradual
* Trigger: rest, exercise, stress
* Radiation: shoulder, arm, jaw
* Associated symptoms: shortness of breath, dizziness, nausea
* Severity and duration

Common non-emergency causes:

* Muscle strain
* Acid reflux
* Anxiety-related chest tightness

When to seek urgent evaluation:

* Chest pain during exertion
* Pain radiating to arm/jaw
* Pain with shortness of breath, sweating, or dizziness

---

### Shortness of Breath

Shortness of breath may accompany:

* Physical overexertion
* Anxiety episodes
* Respiratory infections
* Cardiovascular conditions

Risk indicators:

* Shortness of breath at rest
* New or worsening shortness of breath
* Shortness of breath with chest discomfort or dizziness

---

### Dizziness or Lightheadedness

Possible contexts:

* Dehydration
* Low blood pressure
* Inner ear imbalance
* Fatigue or lack of sleep

Emergency indicators:

* Dizziness accompanied by severe headache
* Fainting
* Chest pain

---

### Fatigue

Common contributing factors:

* Poor sleep quality
* Stress and workload
* Mild infection
* Sedentary lifestyle

Patterns worth noting:

* Duration (acute vs chronic)
* Whether fatigue improves with rest
* Relation to stress or sleep habits

---

## 2. Symptom Interpretation Patterns (Structuring Aid)

These patterns help transform raw text into structured fields.

### Extractable Fields

* Chief complaint
* Symptom list
* Duration (hours, days, weeks)
* Triggers or context
* Severity (mild, moderate, severe)
* Aggravating or relieving factors
* Lifestyle factors (stress, sleep, hydration, exercise)

### Example Interpretation Rules

* "Tightness when exercising" → symptom: chest tightness; trigger: exertion
* "Felt lightheaded after standing" → dizziness related to posture change
* "Hard to breathe when lying down" → notable clinical pattern
* "Pain lasted a few minutes" → short-duration transient symptom

### Non-diagnostic Reminder

No assumptions of medical conditions should be made.
The system provides **summary and guidance**, not diagnosis.

---

## 3. Safe Health Advice Patterns (LLM Output Support)

The AI should follow non-diagnostic, supportive phrasing:

### Recommended Safe Phrasing

* "These symptoms may be influenced by…"
* "It could be helpful to monitor…"
* "You may consider reaching out to a healthcare professional if…"
* "This summary is informational and not a diagnosis."

### Avoid

* Definitive medical statements
* Naming specific diseases
* Treatment recommendations
* Medication or dosage suggestions

### General Safety Guidance

Seek timely medical attention if:

* Symptoms worsen
* Symptoms interfere with daily activities
* New severe symptoms appear
* Chest pain or shortness of breath occurs during exertion

---

## 4. Lifestyle and Environmental Factors

### Common Factors Influencing Symptoms

* Stress and emotional load
* Poor sleep or irregular sleep schedule
* Dehydration
* Low physical activity
* Recent travel or posture changes
* Prolonged screen time

### Patterns to Extract

* Workload: "busy week," "high stress," "long hours"
* Sleep quality: "sleeping 4 hours," "waking up often"
* Hydration: "forgot to drink water"
* Exercise: "started new workout," "no exercise recently"

---

## 5. Structured Summaries (Output Agent Support)

A well-structured health summary includes:

### 1. Overview

* Chief concern
* Symptom pattern in plain language

### 2. Observed Details

* Duration
* Frequency
* Context or triggers

### 3. Contributing Factors

* Stress
* Sleep
* Lifestyle patterns

### 4. Suggested Next Steps

* Monitor symptoms
* Adjust lifestyle factors
* Seek evaluation if symptoms worsen

### 5. Safety Disclaimer

A clear reminder:

> This summary is for informational purposes only and not a medical diagnosis.

---

## 6. Retrieval Formatting for Better LLM RAG Performance

Each section is written in short, self-contained paragraphs to optimize semantic retrieval.

Concept chunks include:

* Symptom definitions
* Interpretation patterns
* Risk indicators
* Safe response rules
* Summary templates

This file is designed to:

* Be easy to embed
* Produce consistent retrieval
* Improve structuring and output quality
* Meet expectations for healthcare-grade RAG systems


