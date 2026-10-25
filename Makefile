.PHONY: setup data baselines train eval demo test all

PYTHON := .venv/Scripts/python.exe
PYTEST := .venv/Scripts/pytest.exe

setup:
	@echo "Setting up virtual environment and dependencies..."
	$(PYTHON) -m pip install -e .

data:
	@echo "Generating synthetic CAD edit dataset..."
	$(PYTHON) scripts/generate_data.py --config configs/data.yaml

baselines:
	@echo "Running evaluation on baseline models..."
	$(PYTHON) scripts/run_baselines.py --config configs/eval.yaml

train:
	@echo "Training patch prediction model..."
	$(PYTHON) scripts/train.py --config configs/train_patch.yaml

eval:
	@echo "Evaluating models on test splits..."
	$(PYTHON) scripts/evaluate.py --config configs/eval.yaml

demo:
	@echo "Launching Gradio interactive CAD patch demo..."
	$(PYTHON) scripts/run_demo.py

test:
	@echo "Running test suite..."
	$(PYTEST) tests/ -v

all: test data baselines train eval
