from fastapi import FastAPI
import httpx
import asyncio

app = FastAPI()

@app.get('/')
def read_root():
    return {'message': 'Hello, World!'}


@app.get('/health-check')
def health_check():
    # Add any additional health check logic if needed
    return {'status': 'OK'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)


