"""
Cliente da Tuya Cloud especializado em disparar códigos IR genéricos
para um Hub Smart IR, sem depender de clonagem de controle físico.

Como funciona (resumo técnico)
-------------------------------
A API Cloud da Tuya para Hubs de IR não tem um endpoint de "enviar hex
NEC cru". Os comandos são entregues via família de endpoints
"learning-codes", que originalmente serve para reenviar códigos que o
Hub *aprendeu* fisicamente. O truque usado aqui: em vez de aprender um
código de um controle real, nós geramos o mesmo formato binário
(base64) algoritmicamente a partir do protocolo NEC padrão
(nec_encoder.py) e o enviamos por esse canal. O Hub não distingue a
origem do código — só entende o payload de pulsos.

Fluxo de chamadas:
1. Primeiro uso (sem remote_id em cache):
   POST /v2.0/infrareds/{infrared_id}/learning-codes
   Cria um "controle virtual" no Hub e retorna um remote_id, já
   disparando o primeiro comando.
2. Usos seguintes (remote_id já conhecido):
   POST /v2.0/infrareds/{infrared_id}/remotes/{remote_id}/learning-codes
   Dispara o código IR em tempo real.

O remote_id é cacheado localmente em .tuya_remote_cache.json para não
precisar recriar o controle virtual a cada execução.
"""
import json
import time
from pathlib import Path

from tuya_connector import TuyaOpenAPI

import codebook
from nec_decoder import decode_tuya_code
from nec_encoder import encode_nec

CACHE_FILE = Path(__file__).parent / ".tuya_remote_cache.json"


class TuyaLearningTimeout(Exception):
    """O Hub não recebeu nenhum sinal IR dentro do tempo limite."""


class TuyaAuthError(Exception):
    pass


class TuyaAPIError(Exception):
    def __init__(self, response):
        self.response = response
        msg = response.get("msg") or response
        code = response.get("code")
        super().__init__(f"Tuya API retornou erro (code={code}): {msg}")


class TuyaIRClient:
    def __init__(self, endpoint: str, access_id: str, access_secret: str, infrared_id: str):
        self.infrared_id = infrared_id
        self.openapi = TuyaOpenAPI(endpoint, access_id, access_secret)
        self._remote_id = None

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------
    def connect(self):
        try:
            resp = self.openapi.connect()
        except Exception as exc:  # erros de rede/timeout do SDK
            raise TuyaAuthError(f"Falha de conexão com {self.openapi.endpoint}: {exc}") from exc

        if not resp or not resp.get("success", False):
            raise TuyaAuthError(
                "Autenticação recusada pela Tuya. Verifique TUYA_ACCESS_KEY, "
                f"TUYA_SECRET_KEY e TUYA_ENDPOINT. Resposta: {resp}"
            )
        return resp

    # ------------------------------------------------------------------
    # Cache do remote_id (controle virtual)
    # ------------------------------------------------------------------
    def _read_cache(self) -> dict:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_remote_id(self, remote_id: str):
        data = self._read_cache()
        data[self.infrared_id] = remote_id
        CACHE_FILE.write_text(json.dumps(data, indent=2))

    def get_remote_id(self):
        if self._remote_id:
            return self._remote_id
        cached = self._read_cache().get(self.infrared_id)
        if cached:
            self._remote_id = cached
        return self._remote_id

    def forget_remote_id(self):
        """Descarta o remote_id em cache (ex: após erro de 'remote not found')."""
        data = self._read_cache()
        data.pop(self.infrared_id, None)
        CACHE_FILE.write_text(json.dumps(data, indent=2))
        self._remote_id = None

    # ------------------------------------------------------------------
    # Provisionamento do controle virtual
    # ------------------------------------------------------------------
    def _provision_remote(self, first_code_b64: str, label: str) -> str:
        path = f"/v2.0/infrareds/{self.infrared_id}/learning-codes"
        body = {
            "codes": [
                {"name": "cli_projetor_aun_et30", "key_name": label, "code": first_code_b64}
            ]
        }
        resp = self.openapi.post(path, body)
        if not resp.get("success"):
            raise TuyaAPIError(resp)

        remote_id = resp["result"]
        self._save_remote_id(remote_id)
        self._remote_id = remote_id
        return remote_id

    # ------------------------------------------------------------------
    # Envio de comando
    # ------------------------------------------------------------------
    def send_ir_code(self, hex_code: str, label: str = "MANUAL", necx2: bool = False) -> dict:
        """
        Envia um código IR NEC (38kHz) bruto para o Hub Smart IR.

        Args:
            hex_code: código NEC em hex (8 dígitos), ex: "00FF02FD" ou "0x00FF02FD".
            label: rótulo usado apenas para log/organização no Hub.
            necx2: True para a variante NECx2 (leader mark de 4500us).

        Returns:
            dict com pelo menos a chave "success" (bool).

        Raises:
            ValueError: código hex mal formatado.
            TuyaAPIError: a Tuya respondeu com success=False.
        """
        code_b64 = encode_nec(hex_code, necx2=necx2)

        remote_id = self.get_remote_id()
        if not remote_id:
            remote_id = self._provision_remote(code_b64, label)
            return {
                "success": True,
                "result": True,
                "provisioned": True,
                "remote_id": remote_id,
            }

        path = f"/v2.0/infrareds/{self.infrared_id}/remotes/{remote_id}/learning-codes"
        resp = self.openapi.post(path, {"code": code_b64})

        if not resp.get("success"):
            # Se o remote_id ficou inválido (ex: apagado no app Tuya),
            # tenta reprovisionar automaticamente uma única vez.
            error_msg = str(resp.get("msg", "")).lower()
            if "remote" in error_msg or resp.get("code") in (2007, 28841002):
                self.forget_remote_id()
                new_remote_id = self._provision_remote(code_b64, label)
                return {
                    "success": True,
                    "result": True,
                    "provisioned": True,
                    "remote_id": new_remote_id,
                    "note": "remote_id anterior era inválido; um novo foi criado.",
                }
            raise TuyaAPIError(resp)

        return resp

    # ------------------------------------------------------------------
    # Reenvio verbatim de um código já capturado (sem passar pelo
    # encoder NEC sintético — usa o payload exatamente como aprendido)
    # ------------------------------------------------------------------
    def send_raw_code(self, code_b64: str, label: str = "RAW") -> dict:
        remote_id = self.get_remote_id()
        if not remote_id:
            remote_id = self._provision_remote(code_b64, label)
            return {"success": True, "result": True, "provisioned": True, "remote_id": remote_id}

        path = f"/v2.0/infrareds/{self.infrared_id}/remotes/{remote_id}/learning-codes"
        resp = self.openapi.post(path, {"code": code_b64})
        if not resp.get("success"):
            error_msg = str(resp.get("msg", "")).lower()
            if "remote" in error_msg or resp.get("code") in (2007, 28841002):
                self.forget_remote_id()
                new_remote_id = self._provision_remote(code_b64, label)
                return {
                    "success": True,
                    "result": True,
                    "provisioned": True,
                    "remote_id": new_remote_id,
                }
            raise TuyaAPIError(resp)
        return resp

    # ------------------------------------------------------------------
    # Captura de código por aprendizado (controle físico -> Hub)
    # ------------------------------------------------------------------
    def enable_learning(self) -> int:
        """
        Coloca o Hub em modo de aprendizado. Retorna o timestamp (t)
        que deve ser usado para consultar o código aprendido.
        """
        path = f"/v2.0/infrareds/{self.infrared_id}/learning-state?state=true"
        resp = self.openapi.put(path, None)
        if not resp.get("success"):
            raise TuyaAPIError(resp)
        return resp.get("t", int(time.time() * 1000))

    def disable_learning(self):
        path = f"/v2.0/infrareds/{self.infrared_id}/learning-state?state=false"
        resp = self.openapi.put(path, None)
        if not resp.get("success"):
            raise TuyaAPIError(resp)

    def poll_learned_code(self, learning_time: int, timeout: float = 20.0, interval: float = 1.5) -> str:
        """
        Consulta repetidamente o Hub até que um código IR tenha sido
        capturado (usuário apertou o botão no controle físico) ou o
        tempo limite seja atingido.

        Returns:
            A string base64 do código capturado.

        Raises:
            TuyaLearningTimeout: nada foi capturado dentro do timeout
                (útil para detectar botões fisicamente quebrados: se
                o Hub não recebe nada, o botão não está transmitindo).
        """
        path = f"/v2.0/infrareds/{self.infrared_id}/learning-codes"
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.openapi.get(path, {"learning_time": learning_time})
            if resp.get("success") and isinstance(resp.get("result"), dict):
                result = resp["result"]
                if result.get("success") and result.get("code"):
                    return result["code"]
            time.sleep(interval)
        raise TuyaLearningTimeout(
            f"Nenhum sinal IR recebido em {timeout:.0f}s. "
            "Se o botão estiver quebrado, isso é esperado — use a inferência."
        )

    def learn_button(self, button_name: str, timeout: float = 20.0) -> dict:
        """
        Fluxo completo: habilita aprendizado, aguarda o usuário apertar
        o botão no controle físico, captura o código, decodifica (se
        possível) e salva no codebook local.

        O chamador (CLI) é responsável por instruir o usuário a apertar
        o botão ANTES ou DURANTE a janela de timeout.
        """
        learning_time = self.enable_learning()
        try:
            code_b64 = self.poll_learned_code(learning_time, timeout=timeout)
        finally:
            try:
                self.disable_learning()
            except TuyaAPIError:
                pass  # não é crítico se falhar ao desligar o modo

        decoded = decode_tuya_code(code_b64)
        codebook.set_entry(
            button_name,
            code_b64=code_b64,
            nec_hex=decoded.hex_code,
            source="learned",
            checksum_ok=decoded.checksum_ok,
        )
        return {
            "code_b64": code_b64,
            "decoded": decoded,
        }

    # ------------------------------------------------------------------
    # Importação de códigos já aprendidos por OUTRO remote_id (ex: um
    # controle virtual criado pelo próprio app Tuya Smart/Smart Life)
    # ------------------------------------------------------------------
    def list_remote_codes(self, remote_id: str) -> list:
        """
        Lista todos os códigos já salvos para um remote_id específico
        (ex: o controle virtual "Projetor" criado pelo app ao aprender
        alguns botões manualmente). Não precisa ser o remote_id que
        este script provisionou — pode ser qualquer remote_id visível
        na sua conta Tuya, desde que pertença ao mesmo Hub
        (infrared_id).

        Returns:
            Lista de dicts: {"name", "key_name", "code", "id"}.
        """
        path = f"/v2.0/infrareds/{self.infrared_id}/remotes/{remote_id}/learning-codes"
        resp = self.openapi.get(path, {})
        if not resp.get("success"):
            raise TuyaAPIError(resp)
        result = resp.get("result")
        return result if isinstance(result, list) else []
