from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import ModeloComDatas, gerenciador_do_dono


class Recorrencia(ModeloComDatas):
    """Molde de um lançamento fixo mensal (aluguel, assinatura, salário).

    Os lançamentos são gerados a partir dele, um por competência. Editar
    "esta e as próximas" encerra este molde (data_fim) e cria outro.
    """

    class Tipo(models.TextChoices):
        RECEITA = "RECEITA", "Receita"
        DESPESA = "DESPESA", "Despesa"

    descricao = models.CharField(max_length=120)
    tipo = models.CharField(max_length=7, choices=Tipo.choices)
    conta = models.ForeignKey("contas.Conta", on_delete=models.PROTECT, related_name="recorrencias")
    categoria = models.ForeignKey("categorias.Categoria", on_delete=models.PROTECT, related_name="recorrencias")
    valor_centavos = models.BigIntegerField()
    dia = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    # Último mês já gerado. A geração só avança, então uma ocorrência
    # excluída ("só esta") nunca é recriada.
    gerada_ate = models.DateField(null=True, blank=True, editable=False)

    objects = gerenciador_do_dono("conta__dono")

    class Meta:
        ordering = ["descricao"]
        constraints = [
            models.CheckConstraint(name="recorrencia_valor_positivo", condition=Q(valor_centavos__gt=0)),
            models.CheckConstraint(name="recorrencia_dia_valido", condition=Q(dia__gte=1, dia__lte=31)),
            models.CheckConstraint(
                name="recorrencia_periodo_valido",
                condition=Q(data_fim__isnull=True) | Q(data_fim__gte=models.F("data_inicio")),
            ),
        ]

    def __str__(self):
        return self.descricao


class Parcelamento(ModeloComDatas):
    """Cabeçalho de uma compra parcelada; cada parcela é um Lancamento."""

    descricao = models.CharField(max_length=120)
    conta = models.ForeignKey("contas.Conta", on_delete=models.PROTECT, related_name="parcelamentos")
    categoria = models.ForeignKey("categorias.Categoria", on_delete=models.PROTECT, related_name="parcelamentos")
    valor_total_centavos = models.BigIntegerField()
    quantidade_parcelas = models.PositiveSmallIntegerField(validators=[MinValueValidator(2), MaxValueValidator(72)])
    data_compra = models.DateField()

    objects = gerenciador_do_dono("conta__dono")

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="parcelamento_valor_cobre_parcelas",
                # Cada parcela precisa de pelo menos 1 centavo.
                condition=Q(valor_total_centavos__gte=models.F("quantidade_parcelas")),
            ),
            models.CheckConstraint(
                name="parcelamento_qtd_valida", condition=Q(quantidade_parcelas__gte=2, quantidade_parcelas__lte=72)
            ),
        ]

    def __str__(self):
        return f"{self.descricao} ({self.quantidade_parcelas}x)"


class Lancamento(ModeloComDatas):
    """Movimento em uma única conta. `valor_centavos` é sempre positivo;
    o `tipo` define se entra ou sai.

    Transferência = dois lançamentos (saída na origem, entrada no destino)
    com o mesmo `transferencia_id`, gravados na mesma transação.
    """

    class Tipo(models.TextChoices):
        RECEITA = "RECEITA", "Receita"
        DESPESA = "DESPESA", "Despesa"
        TRANSF_SAIDA = "TRANSF_SAIDA", "Transferência (saída)"
        TRANSF_ENTRADA = "TRANSF_ENTRADA", "Transferência (entrada)"

    class Status(models.TextChoices):
        PAGO = "PAGO", "Pago"
        PENDENTE = "PENDENTE", "Pendente"

    TIPOS_ENTRADA = (Tipo.RECEITA, Tipo.TRANSF_ENTRADA)
    TIPOS_TRANSFERENCIA = (Tipo.TRANSF_SAIDA, Tipo.TRANSF_ENTRADA)

    tipo = models.CharField(max_length=14, choices=Tipo.choices)
    conta = models.ForeignKey("contas.Conta", on_delete=models.PROTECT, related_name="lancamentos")
    categoria = models.ForeignKey(
        "categorias.Categoria", on_delete=models.PROTECT, null=True, blank=True, related_name="lancamentos"
    )
    descricao = models.CharField(max_length=120)
    valor_centavos = models.BigIntegerField()
    # Data de calendário (sem hora): não sofre conversão de fuso.
    data = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDENTE)

    fatura = models.ForeignKey(
        "cartoes.Fatura", on_delete=models.PROTECT, null=True, blank=True, related_name="lancamentos"
    )
    transferencia_id = models.UUIDField(null=True, blank=True, db_index=True)

    recorrencia = models.ForeignKey(
        Recorrencia, on_delete=models.SET_NULL, null=True, blank=True, related_name="lancamentos"
    )
    # Mês (dia 1º) que o lançamento recorrente representa; evita gerar duas vezes.
    competencia_recorrencia = models.DateField(null=True, blank=True)

    parcelamento = models.ForeignKey(
        Parcelamento, on_delete=models.PROTECT, null=True, blank=True, related_name="parcelas"
    )
    numero_parcela = models.PositiveSmallIntegerField(null=True, blank=True)

    # Reservado para importação de extrato (fora do MVP).
    hash_importacao = models.CharField(max_length=64, null=True, blank=True)

    objects = gerenciador_do_dono("conta__dono")

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["conta", "data"]), models.Index(fields=["categoria", "data"])]
        constraints = [
            models.CheckConstraint(name="lancamento_valor_positivo", condition=Q(valor_centavos__gt=0)),
            models.CheckConstraint(
                name="lancamento_transferencia_consistente",
                condition=(
                    Q(tipo__in=["TRANSF_SAIDA", "TRANSF_ENTRADA"], transferencia_id__isnull=False,
                      categoria__isnull=True)
                    | Q(tipo__in=["RECEITA", "DESPESA"], transferencia_id__isnull=True, categoria__isnull=False)
                ),
            ),
            models.CheckConstraint(
                name="lancamento_parcela_consistente",
                condition=Q(parcelamento__isnull=True, numero_parcela__isnull=True)
                | Q(parcelamento__isnull=False, numero_parcela__gte=1),
            ),
            models.CheckConstraint(
                name="lancamento_recorrencia_tem_competencia",
                condition=Q(recorrencia__isnull=True) | Q(competencia_recorrencia__isnull=False),
            ),
            models.UniqueConstraint(fields=["parcelamento", "numero_parcela"], name="parcela_unica"),
            models.UniqueConstraint(
                fields=["recorrencia", "competencia_recorrencia"], name="recorrencia_uma_vez_por_mes"
            ),
            models.UniqueConstraint(fields=["transferencia_id", "tipo"], name="transferencia_um_par"),
            models.UniqueConstraint(fields=["conta", "hash_importacao"], name="importacao_sem_duplicado"),
        ]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} {self.descricao_completa}"

    @property
    def descricao_completa(self) -> str:
        """Descrição com o número da parcela: "Geladeira (2/10)"."""
        if self.parcelamento_id:
            return f"{self.descricao} ({self.numero_parcela}/{self.parcelamento.quantidade_parcelas})"
        return self.descricao

    @property
    def eh_transferencia(self) -> bool:
        return self.tipo in self.TIPOS_TRANSFERENCIA

    @property
    def eh_entrada(self) -> bool:
        return self.tipo in self.TIPOS_ENTRADA

    @property
    def valor_com_sinal(self) -> int:
        return self.valor_centavos if self.eh_entrada else -self.valor_centavos
