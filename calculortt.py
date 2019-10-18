#!/usr/bin/env python3
import os
import random
import time
from mytcputils import *
from mytcp import Servidor

class CamadaRede:
    def __init__(self):
        self.callback = None
        self.fila = []
    def registrar_recebedor(self, callback):
        self.callback = callback
    def enviar(self, segmento, dest_addr):
        self.fila.append((segmento, dest_addr))

recebido = None
def dados_recebidos(c, dados):
    global recebido
    recebido = dados

conexao = None
def conexao_aceita(c):
    global conexao
    conexao = c
    c.registrar_recebedor(dados_recebidos)

rede = CamadaRede()
dst_port = random.randint(10, 1023)
servidor = Servidor(rede, dst_port)
servidor.registrar_monitor_de_conexoes_aceitas(conexao_aceita)

src_port = random.randint(1024, 0xffff)
seq_no = random.randint(0, 0xffff)
src_addr, dst_addr = '10.%d.1.%d'%(random.randint(1, 10), random.randint(0,255)), '10.%d.1.%d'%(random.randint(11, 20), random.randint(0, 255))
tempo_inicial = time.time()
rede.callback(src_addr, dst_addr, fix_checksum(make_header(src_port, dst_port, seq_no, 0, FLAGS_SYN), src_addr, dst_addr))
tempo_final = time.time()
print(str(tempo_inicial)+' '+str(tempo_final))

