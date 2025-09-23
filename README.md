# KZR - Kay Zero Rebuild

KZR is a conversational AI with an emotional core that influences its memory and responses.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/several-dozen-lizards/KZR.git](https://github.com/several-dozen-lizards/KZR.git)
    cd KZR
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables:**
    -   Copy the example `.env.example` file to a new file named `.env`.
    -   Open the `.env` file and add your OpenAI API key:
        ```
        OPENAI_API_KEY="sk-your-key-here"
        LLM_NAME="Kay"
        ```

## Running the AI

Once setup is complete, run the main script from your terminal:
```bash
python main.py

