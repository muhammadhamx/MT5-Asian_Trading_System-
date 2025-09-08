from channels.middleware import BaseMiddleware

class HTTPSRedirectMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("scheme", "http") == "https":
            # Redirect HTTPS to HTTP
            await send({
                "type": "http.response.start",
                "status": 307,
                "headers": [
                    [b"location", f"http://{scope.get('server', ['127.0.0.1', 8000])[0]}:{scope.get('server', ['127.0.0.1', 8000])[1]}{scope.get('path', '').encode('utf-8')}".encode('utf-8')],
                ]
            })
            await send({"type": "http.response.body"})
            return
        
        return await super().__call__(scope, receive, send)
