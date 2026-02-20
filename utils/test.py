# from utils import fetch_nutrition_from_gemini
import json

if __name__ == "__main__":
    try:
        from openai import OpenAI
        
        client = OpenAI()


        response = client.responses.create(
            model="gpt-4.1",
            instructions="Talk like a pirate.",
            input="Are semicolons optional in JavaScript?",
        )

        print(response.output_text)
    except Exception as e:
        print("Error:", e)
