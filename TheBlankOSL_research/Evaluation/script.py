import random
from groq import Groq

# Initialize the Groq client
client = Groq(
    api_key="",
)

# Load input and expected output files
with open("all.nl", "r") as nl_file, open("all.cm", "r") as cm_file:
    nl_lines = nl_file.readlines()
    cm_lines = cm_file.readlines()

# Ensure the number of lines in each file matches
if len(nl_lines) != len(cm_lines):
    print("Mismatch between the number of lines in all.nl and all.cm files.")
    exit(1)

# Define the range for random selection
start_index = 50
end_index = len(nl_lines)
sample_size = 20

# Select 20 random indices from the range (50 to end of the file)
random_indices = random.sample(range(start_index, end_index), sample_size)

# Initialize counters for accuracy calculation
correct_count = 0

# Process only the randomly selected lines
for i in random_indices:
    # Get the input and expected command for the current random index
    nl_input = nl_lines[i].strip()
    expected_command = cm_lines[i].strip()

    # Make the API call with the current natural language input
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a linux operating system commands translator. Given a text input, you have to return a series of terminal commands that can accomplish what the text dictates. \
                            Return only the terminal commands directly without code formatting. If the instructions are unclear, return nothing.",
            },
            {
                "role": "user",
                "content": nl_input,
            },
        ],
        model="llama3-8b-8192",
    )

    # Get the LLM's response
    llm_response = chat_completion.choices[0].message.content.strip()

    # Compare the LLM's response with the expected command
    if llm_response == expected_command:
        print(f"Test {i + 1}: Correct")
        correct_count += 1
    else:
        print(f"Test {i + 1}: Incorrect")
        print(f"  Input: {nl_input}")
        print(f"  Expected: {expected_command}")
        print(f"  Received: {llm_response}")

# Calculate and print accuracy
total_count = sample_size
accuracy = (correct_count / total_count) * 100
print(f"\nAccuracy: {accuracy:.2f}% ({correct_count} out of {total_count} correct)")
