import os
from engine.loop import KayZero  
from engine.logger import log_message, time_since_last, time_riff, is_time_question

def startup_greeting():
    delta = time_since_last()
    print(time_riff(delta))

def main():
    startup_greeting()
    agent = KayZero(memory_path="memory")
    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n— goodnight.")
            break
        if user.lower() in {"exit", "quit"}:
            print("— goodnight.")
            break
        log_message("user", user)
        out = agent.reply(user)  # <<<<<<<<<<<<<<<<<<<<<<< THIS IS THE FIX!
        log_message("kay", out)
        print("\nKay:", out)

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set; running in offline echo mode.")
    main()
