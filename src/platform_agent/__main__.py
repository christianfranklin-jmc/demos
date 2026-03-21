"""Entry point for running the Platform Agent interactively."""

import sys

from .agent import create_agent


def main() -> None:
    profile_name = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--profile" and i < len(sys.argv) - 1:
            profile_name = sys.argv[i + 1]

    agent = create_agent(profile_name=profile_name)
    print("AWS Platform Agent ready. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        if not user_input:
            continue

        response = agent(user_input)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
