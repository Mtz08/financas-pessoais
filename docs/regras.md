# Regras de negócio

| Situação | Regra |
|---|---|
| Usuários | Cada usuário tem os próprios dados: contas, categorias, lançamentos, cartões, orçamentos e dívidas. Ninguém vê nem altera o que é de outro (ID de outro dono = "não encontrado"). Nomes de conta/categoria são únicos por usuário. |
| Valores | Sempre em centavos inteiros. Entrada no formato `1.234,56`; `10.5` é recusado por ambiguidade. |
| Saldo (corrente/dinheiro) | Saldo inicial + receitas pagas − despesas pagas a partir da data do saldo inicial. Pendente é só previsão. |
| Saldo (cartão) | Toda compra conta como dívida (saldo negativo), paga ou não. Pagamento de fatura reduz a dívida. |
| Transferência | Dois lançamentos (saída e entrada) na mesma transação. Excluir/editar um afeta os dois. |
| Pagamento de fatura | Transferência da conta corrente/dinheiro para o cartão, ligada à fatura. Pagamento total marca as compras como pagas. |
| Fatura | Competência = mês do vencimento. Compra **no dia do fechamento ou depois** vai para a fatura seguinte. |
| Dia 31 / meses curtos | Usa o último dia do mês (31 → 28/02 ou 29/02). Se fechamento e vencimento coincidirem, o fechamento recua um dia. |
| Parcelamento | Valor dividido em partes iguais; a diferença de centavos vai para a última parcela. No cartão, a 1ª parcela segue a regra do fechamento e cada seguinte vai para a próxima fatura. |
| Editar parcelas | Somente esta: qualquer campo. Esta e as próximas / Todas: descrição, categoria, valor e status; data e conta de cada parcela são mantidas. |
| Recorrência | Gera um lançamento por mês até 2 meses à frente. Nunca duplica e nunca recria uma ocorrência excluída. |
| Editar recorrência | Esta e as próximas: encerra o molde no mês anterior e cria um novo. Todas: altera o molde e as pendentes; as já pagas ficam como histórico. |
| Orçamento | Limite mensal por categoria (inclui subcategorias), válido a partir de um mês até ser substituído. Alerta a partir de 80%; "limite atingido" a partir de 100%. |
| Receitas x despesas | Transferências e pagamentos de fatura não contam. Compra no cartão conta na data da compra. |
| Excluir conta/categoria | Bloqueado se houver lançamentos (o banco recusa). Use **Arquivar**: some dos formulários e mantém o histórico. |
| Duplo clique / F5 | Cada formulário tem uma chave única; o segundo envio é ignorado. O botão também é desabilitado no navegador. |
| Backup | JSON só com os dados de quem exporta. Importar substitui só os dados de quem importa, numa única transação (se algo falhar, nada muda); os registros ganham IDs novos. Arquivos da versão antiga continuam aceitos. |
