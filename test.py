from mistralai import Mistral

client = Mistral(api_key="LA_TUA_API_KEY")

response = client.chat.complete(
    model="mistral-small-latest",
    messages=[{"role": "user", "content": "Ciao"}]
)

print(response.choices[0].message.content)
