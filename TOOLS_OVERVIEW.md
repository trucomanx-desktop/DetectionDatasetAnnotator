# YOLO Dataset Tools Overview

This project is composed of three separate applications designed to cover the full workflow of object detection datasets using YOLO models: dataset creation, dataset exploration, and model evaluation. Each tool has a clearly defined responsibility to avoid complexity and maintain simplicity for end users.

---

## 1. detection-dataset-annotator

This is the main annotation tool for YOLO datasets.

### Purpose:
Create and edit object detection labels directly in YOLO format.

### Responsibilities:
- Load datasets structured with `images/` and `labels/` folders
- Display images and existing YOLO bounding boxes
- Allow users to manually draw, edit, and delete bounding boxes
- Save annotations directly in YOLO `.txt` format
- Enforce a predefined class list and consistent class-to-color mapping

### Key principle:
This tool is strictly human-driven. The user is the final authority over all annotations.

### Limitations by design:
- Requires predefined class configuration
- Not designed for flexible or unknown label structures
- No dependency on machine learning models

---

## 2. detection-dataset-labeler

This tool is designed for flexible dataset exploration and labeling when class structure is not known in advance.

### Purpose:
Allow dynamic labeling without predefined class constraints.

### Responsibilities:
- Load images without requiring YOLO label structure
- Allow users to create and name labels dynamically per image
- Assign unique colors automatically to new labels
- Store annotations in a flexible JSON format per image
- <u>Support later conversion from JSON to YOLO or other formats</u>
### Key principle:
This tool prioritizes flexibility over strict dataset structure.

### Limitations by design:
- Does not natively support YOLO dataset format
- Requires conversion step before training models
- Not optimized for standardized machine learning pipelines

---

## 3. yolo-detection-viewer

This tool is designed for model inference visualization and dataset evaluation.

### Purpose:
Compare YOLO model predictions with ground truth annotations for analysis and debugging.

### Responsibilities:
- Load YOLO datasets (images + ground truth labels)
- Run YOLO model inference on images
- Display model predictions as bounding boxes
- Compare predictions against ground truth visually
- Provide toggle options to switch between:
  - Ground truth only
  - Predictions only
  - Combined view (comparison mode)
- Optionally display confidence scores for predictions

### Key principle:
This tool is strictly read-only and evaluation-focused. It does not modify datasets.

### Limitations by design:
- No annotation or label editing functionality
- No saving or modifying of dataset labels
- Used only for inspection, debugging, and model performance analysis

---

## Design Philosophy

The system is intentionally split into three tools to maintain simplicity, clarity, and separation of concerns:

- Annotation (manual dataset creation)
- Labeling (flexible dataset exploration)
- Evaluation (model performance analysis)

Each tool is independent and optimized for a specific stage of the computer vision pipeline, preventing feature overload and maintaining usability for different types of users.
