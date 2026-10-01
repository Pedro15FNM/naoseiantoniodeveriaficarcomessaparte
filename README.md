ATENÇÃO: O nosso programa cria a árvore mapeando dois arquivos csv presentes na pasta 'data', mas o arquivo 'taxa.csv' tem o tamanho maior do que o github aceita, então estamos anexando um link externo para acessar esse arquivo. Para o programa funcionar de maneira completa é necessário baixar ele e colocar na pasta 'data', caso não queira baixar pode usar o parâmetro --fake 1000 ao executar a 'main.py' para simular um cruzamento de dados dos ficheiros e gerar uma árvore falsa.

Link para o arquivo: https://drive.google.com/drive/folders/1xJbYSYOvWb6_E_x2WlgvXXpkQzw0AI4J?usp=drive_link

Esse Link também inclui um vídeo do programa em execução.

### A APLICAÇÃO

Nosso projeto é um jogo de plataforma 2D com visão lateral, no qual o mapa representa visualmente uma Skip List. Cada nó da estrutura é ilustrado como um prédio vertical, onde a quantidade de níveis do nó determina o número de andares do edifício. O jogador se movimenta entre os prédios utilizando tirolesas, que representam graficamente os ponteiros da Skip List.

A base de dados, contendo os animais e suas categorias, é gerenciada por uma Árvore de Afunilamento (Splay Tree), que possui um nó para cada animal. Já a Skip List possui um nó referente a cada classe taxonômica presente na base (ou seja, cada prédio representa uma classe distinta).

No início de cada rodada, um animal é sorteado da Árvore de Afunilamento e suas informações são exibidas. O objetivo do jogador é alcançar o prédio referente à classe desse animal navegando pelas tirolesas (começando pela cabeça da lista), com cuidado para não esgotar a energia de movimentação(tem uma quantidade limitada de movimentos por rodada, se gastar toda a energia perde a rodada), e com cuidado para não ultrapassar o prédio da classse alvo(se ultrapassar perde o jogo). Ao alcançar o objetivo, um novo animal de outra classe é sorteado e o ciclo se repete, iniciando uma nova rodada.

### PROCESSO DE DESENVOLVIMENTO

O desenvolvimento iniciou com a ideação do jogo logo após a apresentação da proposta do projeto. Em seguida, focamos no polimento da ideia, com debates sobre as características da aplicação, definição do escopo e criação dos primeiros diagramas e documentos de conceito.

Muitas ideias iniciais evoluíram. A escolha da base de dados, por exemplo, foi um desafio. Como queríamos integrar uma mecânica de combate, buscamos inicialmente bases contendo monstros de RPG (como _Dungeons & Dragons_), mas nenhuma possuía o volume de dados necessário. A própria mecânica de combate, que originalmente seguiria um estilo "RPG de turnos" sempre que o jogador alcançasse o nó objetivo, foi simplificada para uma resolução rápida via "cara ou coroa" (50/50).

Tecnicamente, a intenção inicial era desenvolver o jogo na engine Unity. Contudo, percebemos rapidamente que a ferramenta era superdimensionada para o escopo do nosso MVP. Optamos então por utilizar a linguagem Python em conjunto com a biblioteca Pygame.

Além do Pygame, a aplicação se apoiou em bibliotecas nativas do Python: `csv` para leitura dos dados, `pickle` para persistência em cache, `unittest` para garantia de qualidade e `hashlib`/`os`/`pathlib` para o gerenciamento e validação de arquivos. O projeto foi construído de maneira incremental: primeiro validamos os dados básicos e as estruturas (Splay Tree e Skip List) de forma isolada, para então integrá-las ao motor do jogo e à interface gráfica, passando por rodadas contínuas de testes e refatorações até chegarmos à versão final. 
