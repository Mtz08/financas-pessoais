// Comportamentos globais. Sem script inline: o CSP só permite arquivos do próprio site.
document.addEventListener("DOMContentLoaded", () => {
  // 1) Anti duplo clique: ao enviar, desabilita os botões do formulário.
  //    (O servidor também recusa o reenvio via chave de idempotência.)
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      if (form.dataset.enviando) {
        evento.preventDefault();
        return;
      }
      form.dataset.enviando = "1";
      form.querySelectorAll("button[type=submit], button:not([type])").forEach((botao) => {
        botao.setAttribute("aria-busy", "true");
        // Desabilitar só depois do envio começar, senão o botão não vai no POST.
        setTimeout(() => { botao.disabled = true; }, 0);
      });
    });
  });

  // 2) Confirmação antes de ações destrutivas.
  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      if (!window.confirm(form.dataset.confirmar)) {
        evento.preventDefault();
        evento.stopImmediatePropagation();
      }
    }, { capture: true });
  });

  // 3) "Cancelar" volta para a página anterior.
  document.querySelectorAll("[data-voltar]").forEach((link) => {
    link.addEventListener("click", (evento) => {
      if (window.history.length > 1) {
        evento.preventDefault();
        window.history.back();
      }
    });
  });

  // 4) Formulário de conta: campos de cartão só aparecem para tipo = cartão.
  const tipo = document.querySelector("select[name=tipo]");
  const camposCartao = document.querySelectorAll("div[data-so-cartao]");
  if (tipo && camposCartao.length) {
    const atualizar = () => camposCartao.forEach((campo) => { campo.hidden = tipo.value !== "CARTAO"; });
    tipo.addEventListener("change", atualizar);
    atualizar();
  }
});
