## Overview

The primary goal of this project is to assess how accurately and consistently the app generates terminal commands in response to natural language input. The evaluation plan includes:
- Using the NL2Bash dataset as a standard benchmark.
- Measuring exact match accuracy between generated commands and expected commands.
- Testing the app’s robustness by rephrasing inputs in various contexts (e.g., student or finance personas).
- Exploring advanced evaluation methods to account for command variations that achieve the same execution results.

## Evaluation Methodology

### Step 1: Exact Match Accuracy with NL2Bash

We start by using the **NL2Bash dataset** as a benchmark:
1. Each input from the dataset is passed to the LLM to generate a corresponding terminal command.
2. The generated command is compared to the expected command in the dataset.
3. If the commands match exactly, the output is marked as accurate; otherwise, it is marked as inaccurate.

**Metric**: The accuracy score is calculated as the percentage of exact matches out of all test cases.

### Step 2: Robustness Testing with Rephrased Inputs

To test the model’s ability to handle varied inputs, we rephrase the original NL2Bash inputs to simulate different user personas (e.g., student, finance, tech). Rephrased inputs maintain the same intent, and the expected output remains the same.

For each rephrased input:
1. The input is passed to the LLM to generate a command.
2. The generated command is compared to the original expected command from NL2Bash.

**Goal**: To verify if the app can accurately interpret different input phrasings and maintain a high accuracy rate.

### Step 3: Evaluating Execution Equivalence

Since two syntactically different commands may achieve the same result, we explore methods for flexible evaluation:
- **Edit Distance (Levenshtein Distance)**: Measures similarity between the generated and expected command, allowing for slight variations.
- **Command Execution Equivalence Testing**: Both the generated command and the expected command are executed in a sandbox (e.g., Docker), and outputs or final states (such as file creation or folder structure) are compared.
- **Regular Expression Matching**: For commands with flexible syntax (e.g., ordering of options), regex-based matching allows acceptable variations.

## Future Enhancements

1. **Advanced Input Contexts**: Expanding persona-based testing (e.g., more specialized vocabulary or instructions) to further evaluate the model’s adaptability.
2. **Automated Execution Validation**: Integrating command execution equivalence tests in a sandbox environment to verify results beyond exact text matching.
3. **CI/CD Pipeline Integration**: Incorporating tests into a CI/CD pipeline to monitor accuracy across versions and track model improvements over time.

## Results and Metrics

Upon completion, the tests generate a report with the following metrics:
- **Exact Match Accuracy**: Percentage of correct matches from NL2Bash.
- **Rephrased Input Accuracy**: Accuracy rate for varied phrasing.
- **Execution Equivalence Score** (optional): Percentage of generated commands that achieve the same result as the expected command, even if not identical.
