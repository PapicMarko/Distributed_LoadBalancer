from fastapi import FastAPI, HTTPException
import httpx
import asyncio

app = FastAPI()

@app.get('/')
def read_root():
    return {'message': 'Hello, World!'}


@app.get('/health-check')
def health_check():
    return {'status': 'OK'}

@app.get('/health-check')
def health_check():
    raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)


