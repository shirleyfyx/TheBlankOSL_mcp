# The Blank OSL (The Blank Operating System Layer)

_Project category:_ Advanced Technology

_Team name:_ Vertex

_Team members (by last name):_

-   Pouria Amini (pamini)
-   Shirley Fang (y266fang)
-   Evan He (e7he)
-   Tony Li (t392li)
-   Alan Zhu (c63zhu)


## Abstract

The Blank Operating System Layer is a user interface that makes operating system navigation and control more expressive and intuitive. It consists of a large language model, a single client, and multiple servers that communicate through the Model Context Protocol, with each message written in JavaScript Object Notation format.
The large language model can be provided by an existing system such as ChatGPT, Google Gemini, or a self-hosted local model.
Each server is responsible for a specific group of related functions. For example, one server may handle reading and writing to the file system, while another may provide weather information from the internet. Every server exposes the purpose of its available functions, along with parameter types and return values, in a format that follows the Model Context Protocol standard. This design restricts the large language model to these specific functions, and any invalid function calls or parameters are rejected by the server.
The client provides a terminal-style interface that allows users to issue tasks in natural language through typing in the text entry or using the speech-to-text feature. When a task is submitted, the client forwards it to the large language model, which interprets the user’s intent and converts it into a single Model Context Protocol message. If the task cannot be performed based on the available servers, the large language model rejects it and returns an error. If the task is ambiguous, such as creating a temporary file, the large language model may ask for additional details, including the file’s name, type, and lifetime in a conversation dialog. Once the client receives the message from the large language model, it displays the task details, including the operation to perform, generated parameters, required permissions, and server dependencies, on a dialog, for the user to review. The user can type yes to continue or no to cancel. If the user chooses to continue, the client sends the message to the appropriate server, which executes the task.
Third-party applications with Model Context Protocol library installed, can interact with the client through its exposed application interface. For instance, it may directly send a task to the client as if the user types in the text entry.
