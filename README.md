# Python Monorepo POC

This project is a proof-of-concept demonstrating a Python monorepo structure where multiple independent libraries are consumed by a separate application.

- `my_monorepo`: Contains the individual libraries (`adder`, `subtractor`).
- `consumer_app`: A separate application that uses the libraries from the monorepo, managed with Poetry.

## Requirements

- [Python](https://www.python.org/) (Version 3.12+ is recommended)
- [Poetry](https://python-poetry.org/) for dependency management.

## Local Setup and Testing

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

If you haven't already, clone the repository to your local machine.

```bash
git clone https://github.com/Think-and-Dev/python-library-poc
cd python-library-poc
```

### 2. Navigate to the Consumer App

All commands should be run from within the `consumer_app` directory.

```bash
cd consumer_app
```

### 3. Install Dependencies

This project uses Poetry to manage dependencies and link the local libraries from the monorepo.

If this is your first time setting up the project, you need to add the local packages using their paths. Poetry will create a virtual environment and install them in "editable" mode.

```bash
# Add the adder library
poetry add --editable ../my_monorepo/packages/adder

# Add the subtractor library
poetry add --editable ../my_monorepo/packages/subtractor
```

**Note:** If the `pyproject.toml` and `poetry.lock` files in `consumer_app` already list these dependencies (because someone else has already run the `add` commands and committed the files), you can just run:

```bash
poetry install
```

### 4. Run the Application

Use `poetry run` to execute the main script inside the Poetry-managed virtual environment.

```bash
poetry run python main.py
```

You should see the following output, confirming that the consumer app is successfully using both libraries:

```
Addition result: 15
Subtraction result: 5
```
