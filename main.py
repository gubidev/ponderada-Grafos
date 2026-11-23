# =============================================================================
# Ponderada - Smart Grid: rota de emergência (Dijkstra) e rede mínima (Prim)
#
# Como rodar:   python main.py
# Como salvar a saída num arquivo:   python main.py > saida.txt
#
# Organização do arquivo (de cima para baixo):
#   1. CONFIGURAÇÃO ........ RA, origem e ramal da contingência
#   2. TAD Grafo ........... matriz de adjacência e suas operações
#   3. dijkstra() e rota() . caminho mínimo e reconstrução da rota
#   4. prim() .............. árvore geradora mínima (MST)
#   5. pesos_do_ra() ....... as 13 fórmulas do enunciado
#   6. impressão ........... funções que montam as tabelas
#   7. main() .............. junta tudo e responde as questões
# =============================================================================


# =============================================================================
# 1. CONFIGURAÇÃO - é aqui que se mexe se o professor mudar o enunciado
# =============================================================================

# Aqui colocamos o RA. Cada caractere vira um dígito, na ordem:
#   RA = 5 1 0 1 0 8
#        D1 D2 D3 D4 D5 D6
# Esses dígitos entram nas fórmulas dos pesos (função pesos_do_ra) e o D6
# também decide o destino (função escolher_destino).
# Se o professor der outro RA, basta trocar esta linha e rodar de novo:
# pesos, matriz, Dijkstra, contingência e Prim são todos recalculados.
RA = "510108"

# Origem do Dijkstra. Os vértices são numerados pelo índice:
#   S0 -> 0, S1 -> 1, ..., S7 -> 7
# O enunciado pede origem S0, então ORIGEM = 0.
# Se pedirem sair de S3, por exemplo, troque para ORIGEM = 3.
ORIGEM = 0

# Ramal que "cai" na Questão 2 (contingência). Usamos o NOME da aresta
# (e1..e13) e o código descobre sozinho quais subestações ela liga.
# O enunciado derruba o e5 = (S2, S4). Se pedirem outro, troque aqui.
RAMAL_CONTINGENCIA = "e5"

# Dois "valores especiais" com papéis diferentes. Não confundir:
#
#   NULO = None  -> usado DENTRO DA MATRIZ: "não existe ramal entre i e j".
#                   Não usamos 0 porque 0 poderia ser um peso válido.
#
#   INF = inf    -> usado no vetor de distâncias L do Dijkstra (e na chave
#                   do Prim): "ainda não sei chegar nesse vértice".
#                   float("inf") é maior que qualquer número, então a
#                   comparação "novo < L[v]" funciona sem caso especial.
INF = float("inf")
NULO = None


# =============================================================================
# 2. TAD GRAFO - matriz de adjacência
# =============================================================================

class Grafo:
    """Grafo não orientado e ponderado, representado por matriz de adjacência.

    M é uma matriz n x n. M[i][j] guarda o peso (km) do ramal entre Si e Sj,
    ou NULO se não existe ramal. Como o grafo é não orientado (o cabo serve
    nos dois sentidos), sempre vale M[i][j] == M[j][i]: a matriz é simétrica.
    """

    def __init__(self, n, nomes=None):
        # n = quantidade de vértices (subestações). No enunciado, n = 8.
        self.n = n
        # Se ninguém passar nomes, gera "S0", "S1", ..., "S{n-1}".
        self.nomes = nomes or [f"S{i}" for i in range(n)]
        # Cria a matriz inteira com NULO (nenhum ramal ainda).
        # Usamos list comprehension para que cada linha seja uma lista
        # DIFERENTE. Fazer [[NULO] * n] * n criaria n referências para a
        # MESMA linha, e mudar M[0][1] mudaria todas as linhas.
        self.M = [[NULO] * n for _ in range(n)]

    def adicionar_aresta(self, i, j, peso):
        # Rejeitamos peso negativo porque o Dijkstra só é correto com pesos
        # >= 0. Ele assume que, depois de fechar um vértice, nenhum caminho
        # futuro pode ficar mais curto. Com peso negativo isso deixa de ser
        # verdade e o resultado pode sair errado. Também não faz sentido
        # físico: distância de cabo não é negativa.
        if peso is None or peso < 0:
            raise ValueError(f"Peso inválido em ({self.nomes[i]}, {self.nomes[j]}): {peso}")
        # Grava nas DUAS posições para manter a simetria (não orientado).
        self.M[i][j] = peso
        self.M[j][i] = peso

    def remover_aresta(self, i, j):
        # Remover = voltar a NULO nas duas posições. Se limpássemos só
        # M[i][j], a matriz ficaria assimétrica e o ramal continuaria
        # existindo no sentido j -> i.
        self.M[i][j] = NULO
        self.M[j][i] = NULO

    def peso(self, i, j):
        # Devolve o peso do ramal (i, j), ou NULO se não houver ramal.
        return self.M[i][j]

    def vizinhos(self, i):
        # Vizinhos de i = todos os j cuja célula M[i][j] tem peso.
        # Na matriz de adjacência isso exige varrer a linha inteira: O(n).
        return [j for j in range(self.n) if self.M[i][j] is not NULO]

    def eh_simetrica(self):
        # Conferência pedida na Etapa 1: compara cada M[i][j] com M[j][i].
        return all(self.M[i][j] == self.M[j][i] for i in range(self.n) for j in range(self.n))

    def copia(self):
        # Cópia independente do grafo, usada na contingência para remover
        # o ramal sem estragar o grafo original.
        # linha[:] copia cada linha. Se fizéssemos só g.M = self.M, os dois
        # grafos dividiriam a mesma matriz e remover em um removeria no outro.
        g = Grafo(self.n, self.nomes)
        g.M = [linha[:] for linha in self.M]
        return g

    def imprimir_matriz(self):
        # Cabeçalho com os nomes das colunas, cada um ocupando 6 caracteres
        # alinhados à direita (:>6), para a matriz sair alinhada.
        print("      " + "".join(f"{s:>6}" for s in self.nomes))
        for i in range(self.n):
            # Onde não há ramal, mostra um traço em vez de "None".
            celulas = "".join(f"{'—' if v is NULO else v:>6}" for v in self.M[i])
            print(f"{self.nomes[i]:>6}{celulas}")


# =============================================================================
# 3. DIJKSTRA - caminho de menor custo a partir de uma origem
# =============================================================================

def dijkstra(g, origem, destino=None):
    """Retorna (L, ant, ordem_de_fechamento, trace).

    L[v]     -> menor distância conhecida da origem até v
    ant[v]   -> de qual vértice chegamos em v nesse caminho (antecessor)
    ordem    -> ordem em que os vértices foram fechados
    trace    -> um registro por iteração, usado para imprimir o teste de mesa

    Desempate: entre abertos com o mesmo L, fecha o de menor índice.
    Se destino for dado, para assim que ele é fechado (igual ao teste de mesa).
    Se destino for None, roda até fechar todos (usado na Questão 3).
    """
    # Inicialização: ninguém é alcançado (INF), ninguém tem antecessor,
    # ninguém está fechado. A origem começa com distância 0.
    L = [INF] * g.n
    ant = [None] * g.n
    fechado = [False] * g.n
    L[origem] = 0
    ordem, trace = [], []

    while True:
        # "Abertos" = vértices que já alcançamos (L < INF) mas ainda não
        # fechamos. Vértice com L = INF ainda não foi descoberto.
        abertos = [v for v in range(g.n) if not fechado[v] and L[v] < INF]
        if not abertos:
            break  # Nada mais a explorar (ou o grafo é desconexo).

        # Escolha gulosa: pega o aberto com MENOR L.
        # A chave (L[v], v) é uma tupla: o Python compara primeiro L[v] e,
        # só se empatar, compara v. Assim o empate é resolvido pelo menor
        # índice, que é a regra do enunciado.
        u = min(abertos, key=lambda v: (L[v], v))

        # Fechar u: a partir daqui L[u] é DEFINITIVO. Como todos os pesos
        # são >= 0, nenhum caminho que passe por outro aberto (todos com
        # L >= L[u]) pode chegar em u por menos.
        fechado[u] = True
        ordem.append(u)

        # Relaxamento: para cada vizinho v ainda aberto, testa se ir até u
        # e depois atravessar o ramal (u, v) é melhor que o L[v] atual.
        atualizados = []
        for v in g.vizinhos(u):
            if not fechado[v] and L[u] + g.peso(u, v) < L[v]:
                L[v] = L[u] + g.peso(u, v)
                ant[v] = u  # o melhor caminho até v agora passa por u
                atualizados.append((v, u, L[v]))

        # Guarda uma "foto" desta iteração para a tabela do teste de mesa.
        # L[:] e fechado[:] são CÓPIAS. Sem copiar, todas as linhas do
        # trace apontariam para a mesma lista e mostrariam só o estado final.
        trace.append((u, L[u], L[:], fechado[:], atualizados))

        # O teste de mesa termina quando o destino é fechado.
        if u == destino:
            break

    return L, ant, ordem, trace


def rota(ant, destino):
    # Reconstrói o caminho andando de trás para frente pelos antecessores:
    #   S7 -> ant[S7] = S6 -> ant[S6] = S3 -> ant[S3] = S1 -> ant[S1] = S0
    # A origem tem ant = None, e é aí que o laço para.
    # No fim invertemos ([::-1]) para ficar na ordem origem -> destino.
    caminho = []
    v = destino
    while v is not None:
        caminho.append(v)
        v = ant[v]
    return caminho[::-1]


# =============================================================================
# 4. PRIM - árvore geradora mínima (MST)
# =============================================================================

def prim(g, raiz=0):
    """Retorna (lista de arestas da MST, custo total). Desempate por menor índice.

    O Prim é quase o mesmo código do Dijkstra. A diferença está em UMA linha:
      Dijkstra: L[v]     = L[u] + peso(u, v)   (distância acumulada desde a origem)
      Prim:     chave[v] = peso(u, v)          (só o custo do cabo que liga v à árvore)
    Por isso o Dijkstra minimiza o caminho até a origem e o Prim minimiza a
    soma total de cabos.
    """
    na_arvore = [False] * g.n   # equivalente ao "fechado" do Dijkstra
    chave = [INF] * g.n         # menor ramal conhecido ligando v à árvore
    pai = [None] * g.n          # outra ponta desse ramal (como o ant)
    chave[raiz] = 0
    arestas = []

    # Uma árvore com n vértices tem exatamente n - 1 arestas. O laço roda n
    # vezes: a 1a iteração só coloca a raiz, as outras n - 1 adicionam um
    # ramal cada.
    for _ in range(g.n):
        # Escolhe, fora da árvore, o vértice com o ramal mais barato até ela.
        # Mesmo desempate do Dijkstra: menor chave, depois menor índice.
        u = min((v for v in range(g.n) if not na_arvore[v]), key=lambda v: (chave[v], v))
        na_arvore[u] = True
        if pai[u] is not None:  # a raiz não tem pai, então não gera aresta
            arestas.append((pai[u], u, g.peso(pai[u], u)))
        # Atualiza as chaves dos vizinhos com o peso do ramal (u, v), SEM
        # somar nada acumulado. Esta é a diferença para o Dijkstra.
        for v in g.vizinhos(u):
            if not na_arvore[v] and g.peso(u, v) < chave[v]:
                chave[v] = g.peso(u, v)
                pai[v] = u

    return arestas, sum(p for _, _, p in arestas)


# =============================================================================
# 5. PARAMETRIZAÇÃO PELO RA - as 13 fórmulas do enunciado
# =============================================================================

def pesos_do_ra(ra):
    # Separa o RA em 6 dígitos inteiros. Para "510108":
    #   D1=5, D2=1, D3=0, D4=1, D5=0, D6=8
    D1, D2, D3, D4, D5, D6 = (int(c) for c in ra)

    # Cada entrada é: nome -> (vértice i, vértice j, peso).
    # Os vértices são índices (S0 = 0, ..., S7 = 7).
    # "mod" do enunciado é o operador % do Python (resto da divisão).
    # Ao lado de cada fórmula, o resultado com o nosso RA 510108.
    # Se o professor mudar uma fórmula, troque só a conta da linha dela.
    return {
        "e1":  (0, 1, 10 + (D6 % 5)),           # 10 + (8 % 5) = 10 + 3 = 13
        "e2":  (0, 2, 15 + (D5 % 7)),           # 15 + (0 % 7) = 15 + 0 = 15
        "e3":  (1, 2, 8 + (D4 % 4)),            #  8 + (1 % 4) =  8 + 1 =  9
        "e4":  (1, 3, 12 + (D3 % 6)),           # 12 + (0 % 6) = 12 + 0 = 12
        "e5":  (2, 4, 14 + (D2 % 5)),           # 14 + (1 % 5) = 14 + 1 = 15
        "e6":  (2, 5, 9 + (D1 % 6)),            #  9 + (5 % 6) =  9 + 5 = 14
        "e7":  (3, 4, 7 + ((D5 + D6) % 5)),     #  7 + (8 % 5) =  7 + 3 = 10
        "e8":  (3, 6, 11 + ((D4 + D5) % 6)),    # 11 + (1 % 6) = 11 + 1 = 12
        "e9":  (4, 5, 6 + ((D3 + D4) % 4)),     #  6 + (1 % 4) =  6 + 1 =  7
        "e10": (4, 7, 16 + ((D2 + D3) % 7)),    # 16 + (1 % 7) = 16 + 1 = 17
        "e11": (5, 7, 18 + ((D1 + D2) % 8)),    # 18 + (6 % 8) = 18 + 6 = 24
        "e12": (6, 7, 9 + ((D5 + D1) % 5)),     #  9 + (5 % 5) =  9 + 0 =  9
        "e13": (1, 4, 20 + (D6 % 4)),           # 20 + (8 % 4) = 20 + 0 = 20
    }


def escolher_destino(D6):
    # Regra do enunciado: D6 par -> destino S7; D6 ímpar -> destino S6.
    # No nosso RA, D6 = 8. Como 8 % 2 == 0, ele é par, então o destino é
    # S7 (índice 7). Se o RA terminasse em número ímpar, sairia S6 sozinho.
    return 7 if D6 % 2 == 0 else 6


# =============================================================================
# 6. IMPRESSÃO - monta as tabelas no mesmo formato do teste de mesa
# =============================================================================

def fmt(x):
    # Mostra infinito como o símbolo matemático, igual à tabela feita à mão.
    return "∞" if x == INF else str(x)


def imprimir_trace(g, trace, origem):
    # Imprime a tabela do Dijkstra em Markdown, uma linha por iteração.
    # Valores entre colchetes [x] = vértice já fechado naquela iteração.
    nomes = g.nomes
    print("| Iter. | u | L[u] | " + " | ".join(f"L[{s}]" for s in nomes) + " | Antecessores atualizados |")
    # Colunas: Iter, u, L[u], uma por vértice e Antecessores = n + 4.
    print("|" + "---|" * (len(nomes) + 4))
    # Linha de inicialização: 0 na origem e ∞ em todos os outros.
    inicial = ["0" if v == origem else "∞" for v in range(g.n)]
    print("| Inic. | — | — | " + " | ".join(inicial) + f" | Inicialização na origem {nomes[origem]} |")
    for it, (u, Lu, L, fechado, atualizados) in enumerate(trace, 1):
        cel = [f"[{fmt(L[v])}]" if fechado[v] else fmt(L[v]) for v in range(g.n)]
        # Para cada antecessor atualizado, mostra a conta feita: L[u] + peso = novo L[v].
        ants = ", ".join(f"Ant[{nomes[v]}] = {nomes[p]} ({Lu} + {g.peso(p, v)} = {nv})"
                         for v, p, nv in atualizados) or "nenhum"
        print(f"| {it} | {nomes[u]} | {Lu} | " + " | ".join(cel) + f" | {ants} |")


# =============================================================================
# 7. MAIN - executa tudo na ordem das etapas do enunciado
# =============================================================================

def main():
    # ---- Etapa 1: dígitos do RA, destino e montagem do grafo ---------------
    D = [int(c) for c in RA]            # D[0] = D1, ..., D[5] = D6
    destino = escolher_destino(D[5])    # D[5] é o D6
    pesos = pesos_do_ra(RA)

    # Cria o grafo com 8 subestações e insere os 13 ramais.
    g = Grafo(8)
    for nome, (i, j, w) in pesos.items():
        g.adicionar_aresta(i, j, w)

    print(f"RA = {RA}  ->  " + ", ".join(f"D{k+1}={d}" for k, d in enumerate(D)))
    print(f"Origem = {g.nomes[ORIGEM]} | Destino = {g.nomes[destino]} (D6 = {D[5]} é {'par' if D[5] % 2 == 0 else 'ímpar'})\n")

    print("== Pesos (km) ==")
    for nome, (i, j, w) in pesos.items():
        print(f"  {nome:>3}  ({g.nomes[i]}, {g.nomes[j]}) = {w}")

    print("\n== Matriz de adjacência 8x8 (— = NULO) ==")
    g.imprimir_matriz()
    print(f"Simétrica? {g.eh_simetrica()} | Todos os pesos >= 0? {all(w >= 0 for *_, w in pesos.values())}")

    # ---- Etapa 2/3 e Questão 1: Dijkstra da origem até o destino -----------
    # Para quando o destino é fechado, exatamente como no teste de mesa,
    # para as duas tabelas poderem ser comparadas linha a linha.
    L, ant, ordem, trace = dijkstra(g, ORIGEM, destino)
    print(f"\n== Teste de mesa (Dijkstra a partir de {g.nomes[ORIGEM]}, até fechar o destino) ==")
    imprimir_trace(g, trace, ORIGEM)
    custo = L[destino]
    caminho = rota(ant, destino)
    print(f"\nCusto mínimo {g.nomes[ORIGEM]} -> {g.nomes[destino]}: {custo} km")
    print("Rota ótima: " + " -> ".join(g.nomes[v] for v in caminho))
    print("Ordem de fechamento: " + ", ".join(g.nomes[v] for v in ordem))

    # ---- Questão 2: contingência (queda de um ramal) -----------------------
    # Procura no dicionário quais vértices o ramal liga. Para e5: (2, 4) = (S2, S4).
    a, b, _ = pesos[RAMAL_CONTINGENCIA]
    # Trabalha numa CÓPIA para o grafo original continuar intacto para o Prim.
    g2 = g.copia()
    g2.remover_aresta(a, b)  # equivale a fazer o peso virar ∞
    L2, ant2, ordem2, trace2 = dijkstra(g2, ORIGEM, destino)
    custo2 = L2[destino]
    print(f"\n== Contingência: ramal {RAMAL_CONTINGENCIA} ({g.nomes[a]}, {g.nomes[b]}) removido ==")
    imprimir_trace(g2, trace2, ORIGEM)
    if custo2 == INF:
        # Pode acontecer se o professor derrubar um ramal que era a única
        # ligação até o destino (ex.: num grafo com ponte).
        print(f"\n{g.nomes[destino]} ficou inalcançável sem o ramal {RAMAL_CONTINGENCIA}.")
    else:
        print(f"\nNova rota: " + " -> ".join(g2.nomes[v] for v in rota(ant2, destino)) + f" | custo {custo2} km")
        # Acréscimo percentual = (novo - antigo) / antigo * 100
        print(f"Acréscimo: {custo2 - custo} km ({(custo2 - custo) / custo * 100:.2f}%)")

    # ---- Questão 3: Prim (MST) x Dijkstra ----------------------------------
    arestas, total_mst = prim(g, ORIGEM)
    print(f"\n== Prim (MST a partir de {g.nomes[ORIGEM]}) ==")
    for i, j, w in arestas:
        print(f"  ({g.nomes[i]}, {g.nomes[j]}) = {w}")
    print(f"Custo total da MST: {total_mst} km")

    # Dijkstra COMPLETO (sem destino): calcula a distância até todo mundo,
    # para comparar com a MST.
    Lfull, antfull, _, _ = dijkstra(g, ORIGEM)
    print(f"\n== Dijkstra completo a partir de {g.nomes[ORIGEM]} ==")
    for v in range(g.n):
        print(f"  {g.nomes[v]}: {Lfull[v]:>3} km  rota " + " -> ".join(g.nomes[x] for x in rota(antfull, v)))
    print(f"Soma das distâncias de Dijkstra: {sum(Lfull)} km")

    # Árvore de caminhos mínimos: cada vértice ligado ao seu antecessor.
    # Juntando todas as rotas radiais saem n - 1 arestas, que também formam
    # uma árvore, mas NÃO necessariamente a de menor soma de cabos.
    # sorted((v, ant)) põe a aresta em ordem (menor, maior), para (S1,S3) e
    # (S3,S1) contarem como a mesma; o set {} elimina repetidas.
    arv_dij = sorted({tuple(sorted((v, antfull[v]))) for v in range(g.n) if antfull[v] is not None})
    custo_arv_dij = sum(g.peso(i, j) for i, j in arv_dij)
    print("Árvore de caminhos mínimos (união das rotas): "
          + ", ".join(f"({g.nomes[i]},{g.nomes[j]})" for i, j in arv_dij)
          + f" | custo de construção {custo_arv_dij} km")


# Só executa main() quando o arquivo é rodado direto (python main.py),
# e não quando ele é importado por outro arquivo.
if __name__ == "__main__":
    main()
