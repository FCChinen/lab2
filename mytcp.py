import asyncio
import random
import time
from mytcputils import *

def chunked(size, source):
    for i in range(0, len(source), size):
        yield source[i:i+size]

class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            new_seq_no = random.randint(0,0xffff) # Novo SEQ
            new_flags = FLAGS_SYN + FLAGS_ACK # Flag para ACK
            new_ack_no = seq_no + 1; # Novo ACK

            new_segment = fix_checksum(make_header(dst_port, src_port, new_seq_no, new_ack_no, new_flags), dst_addr, src_addr)
            new_seq_no += 1

            # A flag SYN estar setada significa que é um cliente tentando estabelecer uma conexão nova
            # TODO: talvez você precise passar mais coisas para o construtor de conexão
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, new_ack_no, new_seq_no)
            # TODO: você precisa fazer o handshake aceitando a conexão. Escolha se você acha melhor
            # fazer aqui mesmo ou dentro da classe Conexao.
            
            self.rede.enviar(new_segment, src_addr)
            
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, ack_no, seq_no):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.seq_no = ack_no
        self.ack_no = seq_no
        # Estrutura criada para a confirmação dos ACKs
        self.acks_to_confirm = []
        # Estrutura criada para a divisão de segmentos para segmentos maiores que MSS
        self.segmentos = []
        # Ack do último segmento enviado
        self.ack_seg = 0
        # Flag para verificar se há a necessidade de envio de outros segmentos
        self.prox_seg = False
        self.timer = None # asyncio.get_event_loop().call_later(1, self._exemplo_timer)  # um timer pode ser criado assim; esta linha é só um exemplo e pode ser removida
        #self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida

    def _exemplo_timer(self):
        # Esta função é só um exemplo e pode ser removida
        print('Este é um exemplo de como fazer um timer')
        
    def _timer_reenvio(self, segmento, dst_address):
        #Essa função é o timer que reenvia a mensagem
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        self.servidor.rede.enviar(segmento, dst_addr)

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após
        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
        if (flags & FLAGS_FIN) == FLAGS_FIN and (len(payload) == 0): # AQUI
            self.seq_no += 1 # AQUI
            # Envia um segmento de ACK quando receber o FIN
            src_addr, src_port, dst_addr, dst_port = self.id_conexao
            new_segment = fix_checksum(make_header(src_port, dst_port, ack_no, self.seq_no, FLAGS_ACK), dst_addr, src_addr)
            self.servidor.rede.enviar(new_segment, dst_addr)
            # Envia string vazia para o final de uma conexão
            if self.callback:
                self.callback(self, b"")
        
        if (flags & FLAGS_ACK) == FLAGS_ACK:
            # Confirma o ack dos seguimentos que chegaram
            for segmento in self.acks_to_confirm:
                src_addr, src_port, dst_addr, dst_port = self.id_conexao
                _, _, seq_recebido, ack_recebido, _, _, _, _ = read_header(segmento)
                if seq_no == ack_recebido:
                    self.acks_to_confirm.remove(segmento)
                    if self.timer is not None:
                        self.timer.cancel()
            # Verifica o ack do segmento que chegou, se for o mesmo que ele estava esperando, envia os próximos segmentos da mensagem
            if ack_no == self.ack_seg and len(self.segmentos) > 0:
                bloco = self.segmentos.pop(0)
                self.enviar(bloco)

        if seq_no == self.seq_no and len(payload) > 0:
            self.callback(self, payload)
            src_addr, src_port, dst_addr, dst_port = self.id_conexao
            self.seq_no += len(payload)
            new_segment = fix_checksum(make_header(src_port, dst_port, ack_no, self.seq_no, FLAGS_ACK), dst_addr, src_addr)
            self.servidor.rede.enviar(new_segment, dst_addr)
            print('recebido payload: %r' % payload)
            # Pacote com o ACK para confirmação de recebimento de pacote.

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados):
        """
        Usado pela camada de aplicação para enviar dados
        """
        # TODO: implemente aqui o envio de dados.
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        # que você construir para a camada de rede.
        divisao_segmento = 0
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        if (len(dados) <= MSS) and (len(dados) > 0):
            new_header = make_header(src_port, dst_port, self.ack_no, self.seq_no, FLAGS_ACK)
            segmento = fix_checksum(new_header, dst_addr, src_addr) + dados
            self.servidor.rede.enviar(segmento, dst_addr)
            self.timer = asyncio.get_event_loop().call_later(1, self._timer_reenvio, segmento, dst_addr)
            self.ack_no += len(dados)
            self.ack_seg = self.ack_no
            self.acks_to_confirm.append(segmento)
        else:
            # Divide o segmento maior que MSS no new_data
            new_data = list(chunked(MSS, dados))
            for bloco in new_data:
                # Envia o primeiro segmento para a rede
                if divisao_segmento == 0:
                    new_header = make_header(src_port, dst_port, self.ack_no, self.seq_no, FLAGS_ACK)
                    segmento = fix_checksum(new_header, dst_addr, src_addr) + bloco
                    self.acks_to_confirm.append(segmento)
                    self.servidor.rede.enviar(segmento, dst_addr)
                    self.timer = asyncio.get_event_loop().call_later(1, self._timer_reenvio, segmento, dst_addr)
                    self.ack_no += len(bloco)
                    self.ack_seg = self.ack_no
                    divisao_segmento += 1
                # Adiciona na estrutura criada, os blocos segmentados que deve ser enviados
                else:
                    self.segmentos.append(bloco)
                
    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        # TODO: implemente aqui o fechamento de conexão
        
        # Envia a um header com a flag FIN para finalizar a conexão
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        new_header = make_header(src_port, dst_port, self.ack_no, self.seq_no, FLAGS_FIN)
        segmento = fix_checksum(new_header, dst_addr, src_addr)
        self.servidor.rede.enviar(segmento, dst_addr)
        
        # Limpa os atributos, para que não haja mais conexão
        self.servidor = None
        self.id_conexao = None
        self.callback = None
        self.seq_no = None
        self.ack_no = None
