
# DocChainVaildator User guide


Welcome to the DocChainVaildator! This guide will help you setup and use the DocChainVaildator to sign and verify PDF documents.

---

## Installation

The following steps will guide you through the setup process of DocChainValidator on you system. This program will work on windows, Linux and macOS. This program also require you to install python your system. If you currently do not have python installed, you can get the latest version python from [the official Python website](https://www.python.org/downloads/). If you are not sure that you have python installed, you can run `python --version` in your pc's terminal. If you have python, the terminal will output the version of python installed on your pc.

#### Step 1: Download the software.

If you haven't already downloaded the program you can clone if from Github using the following command.

Bash

```text
git clone https://github.com/torporoverload/docchainvalidator.git
cd docchainvalidator
```

If you don't have git installed, you can download the source code as a ZIP file from the repository page and extract it to a location of your choice. you can find the repository [here](https://github.com/TorporOverload/DocChainValidator).

#### Step 2: Create a python venv

Although you can install the required dependencies without a venv, using a virtual environment is a best practice for Python projects as it keeps dependencies isolated.

In order to create a python virtual environment, run the following command in the root directory of docchainvalidator project.

Bash

```text
python -m venv venv
```

To activate the environment, use the following command:

- On mac/linux :

    Bash

    ```text
    source venv/bin/activate
    ```

- On windows:

    Bash

    ```text
    .\venv\Scripts\activate
    ```

#### Step 3: Install dependencies

Once you have the venv activated, you can install the dependecies metioned in the requirements.txt file using the following command:

Bash

```text
pip install -r requirements.txt
```

### Step 4: Run the Application

Once the dependencides have been installed, you can run the program by running the `main.py` script:

Bash

```text
python main.py
```

On the first run, the application will automatically create a `data` directory, which will contain subdirectories for your blockchain data (`blockchain`), encryption keys (`keys`), and logs (`logs`).

If the installation was successful, you will be greeted with the main menu.

---

## Usage

This section explains how to use each feature of the program, accessible from the main menu.

> **Important Note**: It is highly recommended to connect your node to the network (using option **5. Connect to peer**) *before* you start signing and mining new documents. Connecting to the network as soon as possible ensures that your local blockchain is synchronized, which prevents your newly mined blocks from being lost due to potential chain forks.

### 1. Sign a New Document

This option allows you to cryptographically sign a PDF document and add it to the blockchain.

- **Process**: You will be prompted to enter the file path of the PDF you wish to sign. After that, you'll need to provide the username associated with your key pair to authorize the signing.

- **How it works**: The application reads the document page by page. Each page, along with its metadata, is signed using your private key and then added to a mining queue. A background worker will then mine these pages into new blocks on the blockchain.

- **File Support**: This application works by extracting text from your PDF documents. Therefore, **it only supports PDFs with selectable, text-based content**. Scanned documents or PDFs that are purely images without an underlying text layer cannot be processed correctly.

### 2. Verify a Document

Use this option to check the authenticity and integrity of a PDF document against the records stored on the blockchain.

- **Process**: You will be asked to provide the file path of the PDF you want to verify.

- **How it works**: The system first searches the blockchain for a document with a matching title. If not found, it can perform a more in-depth search by comparing the content of your file with the content stored in the entire blockchain. It provides a page-by-page summary, highlighting which pages are verified and which may have been tampered with or are missing from the blockchain.

### 3. Create New Key Pair

This option generates a new RSA public/private key pair, which is essential for signing documents.

- **Process**: You will be prompted to enter a unique alphanumeric username and a secure password (at least 8 characters long).

- **How it works**: The system generates a 4096-bit RSA key pair. The private key is encrypted with your password and saved locally in the `data/keys` directory, along with the public key. These keys are tied to the username you provide.

### 4. Network Status

This displays statistics and information about your connection to the P2P network.

- **Process**: Simply select this option from the menu.

- **What it shows**: You can view your node's unique ID, its connection status, the number of currently connected peers, and the current height of your local copy of the blockchain. This is useful for monitoring the health and sync status of your node.

### 5. Connect to Peer

This option allows you to manually connect your node to another peer on the network.

- **Process**: You'll need to enter the host (IP address) and port number of the peer you want to connect to.

- **How it works**: Your node will send a connection request to the specified peer. Once connected, the nodes will begin to sync their blockchains, ensuring you have the most up-to-date records. This is the first step you should do before signing any document.

### 6. Exit

Select this option to safely shut down the DocChainValidator application.

- **Process**: Choosing this option will terminate the program.

- **How it works**: The application performs a graceful shutdown by saving the current state of the blockchain to a file and closing all active network connections. This ensures no data is lost.

