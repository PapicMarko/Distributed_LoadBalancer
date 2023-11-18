from fastapi import FastAPI
import httpx
import asyncio

app = FastAPI()

async def make_async_request(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text

async def main():
    # Example URLs to make asynchronous requests
    urls = ["https://example.com", "https://example.org", "https://example.net"]

    # Use asyncio.gather to concurrently make asynchronous requests
    responses = await asyncio.gather(*(make_async_request(url) for url in urls))

    # Process the responses as needed
    for url, response_text in zip(urls, responses):
        print(f"Response from {url}:\n{response_text}\n")

@app.get("/")
async def root():
    result = await make_async_request("https://example.com")
    return {"message": result}

# Run the asyncio event loop
asyncio.run(main())
