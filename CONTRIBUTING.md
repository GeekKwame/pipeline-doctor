# Contributing to Pipeline Doctor

Thank you for your interest in contributing to Pipeline Doctor! This document provides guidelines for development setup and contributions.

## Development Setup

### Prerequisites

- **Python 3.11 or later**
- `git`
- A GitHub account (for contributing via pull requests)

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/pipeline-doctor.git
cd pipeline-doctor
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Development Dependencies

```bash
pip install -e ".[dev]"
```

This installs Pipeline Doctor in editable mode along with:
- `pytest` for testing
- `jsonschema` for schema validation

### 4. Verify Installation

```bash
pytest
```

All tests should pass (154/155 tests pass; 1 test has a resource warning that does not affect functionality).

---

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_github_client.py
```

### Run Specific Test

```bash
pytest tests/test_github_client.py::test_get_workflow_run_success
```

### Run with Coverage (Optional)

```bash
pip install pytest-cov
pytest --cov=pipeline_doctor --cov-report=html
```

View coverage report: `open htmlcov/index.html`

---

## Code Style

### Guidelines

- Follow **PEP 8** style guide
- Use **type hints** for function parameters and return values
- Write **docstrings** for public functions and classes
- Keep functions **small and focused**

### Example

```python
def fetch_source_files(
    self,
    owner: str,
    repo: str,
    file_paths: List[str],
) -> Dict[str, any]:
    """
    Fetch source files at the pinned commit SHA.

    Args:
        owner: Repository owner
        repo: Repository name
        file_paths: List of file paths to fetch

    Returns:
        Dictionary containing files and limitations
    """
    # Implementation...
```

---

## Adding Tests

### Test Structure

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names

### Example Test

```python
def test_get_workflow_run_success():
    """Test successful workflow run fetch."""
    # Arrange
    client = FakeGitHubClient(run_data={"id": 12345, "status": "completed"})
    
    # Act
    result = client.get_workflow_run("owner", "repo", 12345)
    
    # Assert
    assert result["id"] == 12345
    assert result["status"] == "completed"
```

### Mocking HTTP Requests

Use Python's `unittest.mock` for mocking HTTP responses:

```python
from unittest.mock import Mock, patch

@patch("urllib.request.urlopen")
def test_api_call(mock_urlopen):
    # Mock HTTP response
    mock_response = Mock()
    mock_response.read.return_value = b'{"key": "value"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Test code that makes HTTP request
    # ...
```

---

## Adding Features

### Before Starting

1. **Open an issue** to discuss the feature
2. **Wait for feedback** from maintainers
3. **Read the roadmap** ([docs/roadmap.md](docs/roadmap.md)) to see if it's already planned

### Implementation Steps

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement the feature** with tests

3. **Run all tests**:
   ```bash
   pytest
   ```

4. **Update documentation** if needed

5. **Commit with descriptive messages**:
   ```bash
   git commit -m "Add feature: description of what changed"
   ```

6. **Push and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

---

## Fixing Bugs

### Reporting Bugs

If you find a bug:

1. **Check existing issues** to avoid duplicates
2. **Open a new issue** with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment (Python version, OS)
   - Error messages (redact tokens/keys)

### Fixing Bugs

1. **Create a bug-fix branch**:
   ```bash
   git checkout -b fix/description-of-bug
   ```

2. **Write a failing test** that reproduces the bug

3. **Fix the bug**

4. **Verify the test passes**:
   ```bash
   pytest tests/test_your_test.py
   ```

5. **Run all tests** to ensure no regressions:
   ```bash
   pytest
   ```

6. **Commit and create a pull request**

---

## Documentation

### Updating Documentation

Documentation is in Markdown format:
- `README.md` — Landing page
- `docs/*.md` — Detailed guides

When adding features, update:
1. Relevant guide in `docs/`
2. `README.md` if needed
3. Docstrings in code

### Documentation Style

- Use **clear, concise language**
- Include **code examples**
- Add **"Why?"** explanations, not just "How?"
- Link to related docs

---

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass (`pytest`)
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Code follows style guidelines
- [ ] Commit messages are descriptive

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Related Issue
Fixes #123

## Changes
- Added feature X
- Fixed bug Y
- Updated documentation Z

## Testing
- Ran pytest: all tests pass
- Manually tested with: [describe manual testing]

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code reviewed for security issues
```

---

## Development Workflow

### Typical Workflow

1. **Sync with upstream**:
   ```bash
   git checkout main
   git pull upstream main
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Make changes and test**:
   ```bash
   # Edit files
   pytest
   ```

4. **Commit changes**:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/my-feature
   # Open PR on GitHub
   ```

6. **Address review feedback**:
   ```bash
   # Make changes
   git add .
   git commit -m "Address review feedback"
   git push origin feature/my-feature
   ```

---

## Testing Locally

### Test with Fake Clients

```bash
python3 examples/diagnose_run.py --fake owner/repo 12345
```

### Test with Real GitHub API

```bash
export GITHUB_TOKEN="ghp_..."
python3 examples/diagnose_run.py --fake owner/repo 12345
```

### Test with Real Grok API (Requires Credits)

```bash
export GITHUB_TOKEN="ghp_..."
export GROK_API_KEY="xai-..."
python3 examples/diagnose_run.py owner/repo 12345
```

---

## Common Development Tasks

### Add a New Redaction Pattern

1. Edit `src/pipeline_doctor/redaction.py`
2. Add pattern to `SecretRedactor.PATTERNS`
3. Add test in `tests/test_redaction.py`

### Add a New GitHub API Endpoint

1. Edit `src/pipeline_doctor/github_client.py`
2. Add method to `GitHubClient`
3. Add corresponding method to `FakeGitHubClient`
4. Add tests in `tests/test_github_client.py`

### Add a New Validation Rule

1. Edit `src/pipeline_doctor/validator.py`
2. Add validation method to `IncidentReportValidator`
3. Add tests in `tests/test_validator.py`

---

## Questions?

If you have questions:

1. Check the [documentation](docs/)
2. Search [existing issues](https://github.com/GeekKwame/pipeline-doctor/issues)
3. Open a new issue with your question

---

## Code of Conduct

Be respectful and constructive in all interactions. We're all here to build something useful together.

---

## License

By contributing to Pipeline Doctor, you agree that your contributions will be licensed under the same license as the project (if one exists; check the repository for license information).

---

## Thank You!

Your contributions help make Pipeline Doctor better for everyone. Thank you for your time and effort!
