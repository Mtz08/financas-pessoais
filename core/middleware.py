class CabecalhosDeSegurancaMiddleware:
    """Content-Security-Policy restritiva: só scripts e estilos do próprio
    site. Mesmo que um texto malicioso escapasse do template, o navegador
    se recusaria a executar script inline (defesa em profundidade contra XSS)."""

    CSP = "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        resposta.setdefault("Content-Security-Policy", self.CSP)
        resposta.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return resposta
