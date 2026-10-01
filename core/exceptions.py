class RegraDeNegocio(Exception):
    """Operação recusada por uma regra do domínio; a mensagem vai para o usuário."""


class EnvioDuplicado(RegraDeNegocio):
    """O mesmo formulário foi enviado mais de uma vez."""
