# Modelo de dados

Valores monetários em **centavos inteiros** (`BIGINT`). Datas de lançamento são
datas de calendário; timestamps (`criado_em`, `atualizado_em`) em UTC.

```mermaid
erDiagram
    CONTA ||--o{ LANCAMENTO : "movimenta"
    CONTA ||--o{ FATURA : "cartão tem"
    CONTA ||--o{ RECORRENCIA : ""
    CONTA ||--o{ PARCELAMENTO : ""
    CATEGORIA ||--o{ CATEGORIA : "pai de"
    CATEGORIA ||--o{ LANCAMENTO : "classifica"
    CATEGORIA ||--o{ ORCAMENTO : "limite"
    CATEGORIA ||--o{ RECORRENCIA : ""
    CATEGORIA ||--o{ PARCELAMENTO : ""
    FATURA ||--o{ LANCAMENTO : "agrupa"
    RECORRENCIA ||--o{ LANCAMENTO : "gera"
    PARCELAMENTO ||--|{ LANCAMENTO : "parcelas"

    CONTA {
        bigint id PK
        varchar nome UK
        varchar tipo "CORRENTE|CARTEIRA|CARTAO"
        bigint saldo_inicial_centavos
        date data_saldo_inicial
        smallint dia_fechamento "só cartão"
        smallint dia_vencimento "só cartão"
        bigint limite_centavos "só cartão"
        bool ativo "arquivar"
    }
    CATEGORIA {
        bigint id PK
        varchar nome
        varchar tipo "RECEITA|DESPESA"
        bigint pai_id FK "null = raiz"
        bool ativo
    }
    FATURA {
        bigint id PK
        bigint conta_id FK
        date competencia "dia 1 do mês de vencimento"
        date data_fechamento
        date data_vencimento
    }
    LANCAMENTO {
        bigint id PK
        varchar tipo "RECEITA|DESPESA|TRANSF_SAIDA|TRANSF_ENTRADA"
        bigint conta_id FK
        bigint categoria_id FK "null só em transferência"
        varchar descricao
        bigint valor_centavos "> 0"
        date data
        varchar status "PAGO|PENDENTE"
        bigint fatura_id FK "só cartão"
        uuid transferencia_id "par saída/entrada"
        bigint recorrencia_id FK
        date competencia_recorrencia
        bigint parcelamento_id FK
        smallint numero_parcela
        varchar hash_importacao "reservado"
    }
    RECORRENCIA {
        bigint id PK
        varchar descricao
        varchar tipo
        bigint conta_id FK
        bigint categoria_id FK
        bigint valor_centavos
        smallint dia "1-31"
        date data_inicio
        date data_fim "null = sem fim"
    }
    PARCELAMENTO {
        bigint id PK
        varchar descricao
        bigint conta_id FK
        bigint categoria_id FK
        bigint valor_total_centavos
        smallint quantidade_parcelas "2-72"
        date data_compra
    }
    ORCAMENTO {
        bigint id PK
        bigint categoria_id FK
        date vigente_desde
        bigint limite_centavos
    }
    CHAVE_IDEMPOTENCIA {
        bigint id PK
        uuid chave UK
        timestamp criada_em
    }
```

## Regras garantidas pelo banco

| Regra | Mecanismo |
|---|---|
| Não excluir conta/categoria com lançamentos | `ON DELETE PROTECT` (arquivar com `ativo=false`) |
| Cartão exige dia de fechamento e vencimento | `CHECK conta_cartao_exige_dias` |
| Valor sempre positivo (o tipo dá o sinal) | `CHECK lancamento_valor_positivo` |
| Transferência não tem categoria; receita/despesa têm | `CHECK lancamento_transferencia_consistente` |
| Transferência = exatamente um par saída/entrada | `UNIQUE (transferencia_id, tipo)` |
| Parcela não se repete | `UNIQUE (parcelamento_id, numero_parcela)` |
| Recorrência gera no máx. 1 lançamento por mês | `UNIQUE (recorrencia_id, competencia_recorrencia)` |
| Uma fatura por cartão por mês | `UNIQUE (conta_id, competencia)` |
| Formulário enviado duas vezes | `UNIQUE chave_idempotencia.chave` |
| Extrato importado duas vezes (futuro) | `UNIQUE (conta_id, hash_importacao)` |

## Regras calculadas (não armazenadas)

- **Saldo da conta** = saldo inicial + Σ entradas − Σ saídas.
- **Valor da fatura** = Σ lançamentos da fatura.
- **Uso do orçamento** = Σ despesas da categoria (e subcategorias) no mês ÷ limite vigente.
