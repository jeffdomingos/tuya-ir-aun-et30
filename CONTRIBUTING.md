*[Read in English (US)](CONTRIBUTING.en.md)*

# Contribuindo

Esse projeto nasceu de uma necessidade bem específica (controlar um
projetor AUN ET30 com dois botões fisicamente quebrados), mas os
códigos IR descobertos aqui provavelmente servem pra outros
projetores — muitos aparelhos baratos vendidos sob marcas diferentes
(AliExpress, Amazon, etc.) reaproveitam o mesmo chip de controle
remoto.

## Como ajudar

- **Seu projetor/controle é parecido e os códigos funcionaram?** Abra
  uma issue contando a marca/modelo exato. Isso ajuda a mapear quais
  aparelhos compartilham esse controle.
- **Achou um botão que falta ou um código errado?** Abra um PR
  atualizando [`IR_CODES.md`](IR_CODES.md) e [`codebook.json`](codebook.json)
  junto — mantenha os dois em sincronia.
- **Testou em outro Hub IR (não-Tuya) ou outra ferramenta?** Relate
  se os timings "de livro" do NEC funcionaram ou se você precisou dos
  timings reais medidos (veja a nota em `IR_CODES.md`) — ajuda a
  entender quão sensível é esse hardware específico.
- **Bugs no código do CLI:** este projeto já passou por vários bugs
  reais documentados na seção 8 do [`README.md`](README.md) — se
  achar mais algum (principalmente algo que só aparece contra
  hardware real, não em testes isolados), PR ou issue são bem-vindos.

## Testando antes de mandar PR

```bash
pip install -r requirements.txt
python3 nec_encoder.py    # roda o auto-teste (round-trip encoder/decoder)
python3 nec_decoder.py
```

Ambos devem terminar com `ROUND-TRIP OK`.

## Código de conduta

Sem formalidade excessiva: seja gentil, assuma boa intenção, e lembre
que quem está lendo provavelmente chegou aqui às 2h da manhã tentando
consertar um controle quebrado, igual a gente.
