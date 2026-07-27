# Resume Training

Provide a brief description of the problem, any background context, and what the change accomplishes.
The YOLOv8 training was stopped midway. We need to recover and continue the training from the last saved epoch without losing progress.

## User Review Required

> [!IMPORTANT]
> To resume training in Ultralytics YOLOv8, we will load `last.pt` (which contains the training state) instead of the base `yolov8n.pt` model, and pass `resume=True` to the `.train()` method.

## Open Questions

- Should we permanently change `train.py` to accept a `--resume` command-line argument, or just create a separate `resume_train.py` script? (The plan assumes updating `train.py` with an argument).

## Proposed Changes

### Training Script

#### [MODIFY] [train.py](file:///c:/Users/Byron%20Dumaya/Downloads/Pig_Tracking/scripts/train.py)
- Import `argparse` to handle a `--resume` flag.
- If `--resume` is passed:
  - Check for the existence of `runs/detect/swine_behavior_v1/weights/last.pt`.
  - Load the model using `YOLO('path/to/last.pt')`.
  - Call `model.train(resume=True)` (this automatically picks up previous training config like epochs, imgsz, etc).
- If `--resume` is NOT passed:
  - Keep the existing behavior (load `yolov8n.pt` and start a new training run).

## Verification Plan

### Automated Tests
- Run `python scripts/train.py --resume` for a short period to verify it successfully picks up the last epoch and continues training.

### Manual Verification
- Check the terminal output to ensure it states "Resuming training from runs\detect\swine_behavior_v1\weights\last.pt".
- Check that the epoch number in the console continues from where it left off instead of starting at epoch 0.
