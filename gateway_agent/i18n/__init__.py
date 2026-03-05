"""
Internationalization (i18n) module for qbridge-gateway.

Provides translation support for 7 languages:
en (English), ko (Korean), ja (Japanese), zh (Chinese Simplified),
de (German), fr (French), es (Spanish)

Usage:
    from gateway_agent.i18n import get_translation
    msg = get_translation("server_starting", "ko", port=8003)
"""

from typing import Optional

SUPPORTED_LANGUAGES = ["en", "ko", "ja", "zh", "de", "fr", "es"]
DEFAULT_LANGUAGE = "en"

# ---------------------------------------------------------------------------
# Translation dictionary
# Keys are organized by category:
#   - server: Server lifecycle messages
#   - connection: Connection/session messages
#   - protocol: Protocol and communication messages
#   - device: Device interface messages
#   - auth: Authentication messages
#   - error: Error messages
#   - cli: CLI messages
#   - status: Status/health messages
# ---------------------------------------------------------------------------

translations: dict[str, dict[str, str]] = {
    # ── Server ──────────────────────────────────────────────────────────
    "server_starting": {
        "en": "Gateway server starting on port {port}",
        "ko": "게이트웨이 서버가 포트 {port}에서 시작합니다",
        "ja": "ゲートウェイサーバーがポート{port}で起動中",
        "zh": "网关服务器正在端口{port}上启动",
        "de": "Gateway-Server startet auf Port {port}",
        "fr": "Démarrage du serveur passerelle sur le port {port}",
        "es": "Servidor de puerta de enlace iniciando en el puerto {port}",
    },
    "server_started": {
        "en": "Gateway server started successfully",
        "ko": "게이트웨이 서버가 성공적으로 시작되었습니다",
        "ja": "ゲートウェイサーバーが正常に起動しました",
        "zh": "网关服务器启动成功",
        "de": "Gateway-Server erfolgreich gestartet",
        "fr": "Serveur passerelle démarré avec succès",
        "es": "Servidor de puerta de enlace iniciado exitosamente",
    },
    "server_stopped": {
        "en": "Gateway server stopped",
        "ko": "게이트웨이 서버가 중지되었습니다",
        "ja": "ゲートウェイサーバーが停止しました",
        "zh": "网关服务器已停止",
        "de": "Gateway-Server gestoppt",
        "fr": "Serveur passerelle arrêté",
        "es": "Servidor de puerta de enlace detenido",
    },
    "server_error": {
        "en": "Server error: {error}",
        "ko": "서버 오류: {error}",
        "ja": "サーバーエラー: {error}",
        "zh": "服务器错误: {error}",
        "de": "Serverfehler: {error}",
        "fr": "Erreur serveur : {error}",
        "es": "Error del servidor: {error}",
    },

    # ── Connection ──────────────────────────────────────────────────────
    "client_connected": {
        "en": "Client connected: {client_id}",
        "ko": "클라이언트 연결됨: {client_id}",
        "ja": "クライアント接続: {client_id}",
        "zh": "客户端已连接: {client_id}",
        "de": "Client verbunden: {client_id}",
        "fr": "Client connecté : {client_id}",
        "es": "Cliente conectado: {client_id}",
    },
    "client_disconnected": {
        "en": "Client disconnected: {client_id}",
        "ko": "클라이언트 연결 해제: {client_id}",
        "ja": "クライアント切断: {client_id}",
        "zh": "客户端已断开: {client_id}",
        "de": "Client getrennt: {client_id}",
        "fr": "Client déconnecté : {client_id}",
        "es": "Cliente desconectado: {client_id}",
    },
    "connection_timeout": {
        "en": "Connection timed out: {client_id}",
        "ko": "연결 시간 초과: {client_id}",
        "ja": "接続タイムアウト: {client_id}",
        "zh": "连接超时: {client_id}",
        "de": "Verbindungszeitüberschreitung: {client_id}",
        "fr": "Délai de connexion dépassé : {client_id}",
        "es": "Tiempo de conexión agotado: {client_id}",
    },
    "max_connections_reached": {
        "en": "Maximum connections reached ({max})",
        "ko": "최대 연결 수에 도달했습니다 ({max})",
        "ja": "最大接続数に達しました ({max})",
        "zh": "已达到最大连接数 ({max})",
        "de": "Maximale Verbindungen erreicht ({max})",
        "fr": "Nombre maximum de connexions atteint ({max})",
        "es": "Se alcanzó el máximo de conexiones ({max})",
    },

    # ── Protocol ────────────────────────────────────────────────────────
    "job_submitted": {
        "en": "Job submitted: {job_id}",
        "ko": "작업 제출됨: {job_id}",
        "ja": "ジョブ送信済み: {job_id}",
        "zh": "作业已提交: {job_id}",
        "de": "Auftrag eingereicht: {job_id}",
        "fr": "Tâche soumise : {job_id}",
        "es": "Trabajo enviado: {job_id}",
    },
    "job_completed": {
        "en": "Job completed: {job_id} ({duration}ms)",
        "ko": "작업 완료: {job_id} ({duration}ms)",
        "ja": "ジョブ完了: {job_id} ({duration}ms)",
        "zh": "作业完成: {job_id} ({duration}ms)",
        "de": "Auftrag abgeschlossen: {job_id} ({duration}ms)",
        "fr": "Tâche terminée : {job_id} ({duration}ms)",
        "es": "Trabajo completado: {job_id} ({duration}ms)",
    },
    "job_failed": {
        "en": "Job failed: {job_id} — {reason}",
        "ko": "작업 실패: {job_id} — {reason}",
        "ja": "ジョブ失敗: {job_id} — {reason}",
        "zh": "作业失败: {job_id} — {reason}",
        "de": "Auftrag fehlgeschlagen: {job_id} — {reason}",
        "fr": "Tâche échouée : {job_id} — {reason}",
        "es": "Trabajo fallido: {job_id} — {reason}",
    },
    "job_queued": {
        "en": "Job queued: {job_id} (position {position})",
        "ko": "작업 대기열에 추가: {job_id} (위치 {position})",
        "ja": "ジョブキュー追加: {job_id} (位置 {position})",
        "zh": "作业已排队: {job_id} (位置 {position})",
        "de": "Auftrag eingereiht: {job_id} (Position {position})",
        "fr": "Tâche en file d'attente : {job_id} (position {position})",
        "es": "Trabajo en cola: {job_id} (posición {position})",
    },
    "invalid_message": {
        "en": "Invalid message format",
        "ko": "잘못된 메시지 형식",
        "ja": "無効なメッセージ形式",
        "zh": "无效的消息格式",
        "de": "Ungültiges Nachrichtenformat",
        "fr": "Format de message invalide",
        "es": "Formato de mensaje inválido",
    },
    "protocol_version_mismatch": {
        "en": "Protocol version mismatch: expected {expected}, got {actual}",
        "ko": "프로토콜 버전 불일치: 예상 {expected}, 실제 {actual}",
        "ja": "プロトコルバージョン不一致: 期待 {expected}、実際 {actual}",
        "zh": "协议版本不匹配: 预期 {expected}，实际 {actual}",
        "de": "Protokollversion stimmt nicht überein: erwartet {expected}, erhalten {actual}",
        "fr": "Incompatibilité de version du protocole : attendu {expected}, reçu {actual}",
        "es": "Versión de protocolo incompatible: esperado {expected}, recibido {actual}",
    },

    # ── Device ──────────────────────────────────────────────────────────
    "device_connected": {
        "en": "QPU device connected: {device}",
        "ko": "QPU 디바이스 연결됨: {device}",
        "ja": "QPUデバイス接続: {device}",
        "zh": "QPU设备已连接: {device}",
        "de": "QPU-Gerät verbunden: {device}",
        "fr": "Appareil QPU connecté : {device}",
        "es": "Dispositivo QPU conectado: {device}",
    },
    "device_disconnected": {
        "en": "QPU device disconnected: {device}",
        "ko": "QPU 디바이스 연결 해제: {device}",
        "ja": "QPUデバイス切断: {device}",
        "zh": "QPU设备已断开: {device}",
        "de": "QPU-Gerät getrennt: {device}",
        "fr": "Appareil QPU déconnecté : {device}",
        "es": "Dispositivo QPU desconectado: {device}",
    },
    "device_calibration": {
        "en": "Device calibration started: {device}",
        "ko": "디바이스 캘리브레이션 시작: {device}",
        "ja": "デバイスキャリブレーション開始: {device}",
        "zh": "设备校准开始: {device}",
        "de": "Gerätekalibrierung gestartet: {device}",
        "fr": "Calibration de l'appareil démarrée : {device}",
        "es": "Calibración del dispositivo iniciada: {device}",
    },
    "no_device_available": {
        "en": "No QPU device available",
        "ko": "사용 가능한 QPU 디바이스 없음",
        "ja": "利用可能なQPUデバイスなし",
        "zh": "没有可用的QPU设备",
        "de": "Kein QPU-Gerät verfügbar",
        "fr": "Aucun appareil QPU disponible",
        "es": "Ningún dispositivo QPU disponible",
    },

    # ── Auth ────────────────────────────────────────────────────────────
    "auth_success": {
        "en": "Authentication successful: {user}",
        "ko": "인증 성공: {user}",
        "ja": "認証成功: {user}",
        "zh": "认证成功: {user}",
        "de": "Authentifizierung erfolgreich: {user}",
        "fr": "Authentification réussie : {user}",
        "es": "Autenticación exitosa: {user}",
    },
    "auth_failed": {
        "en": "Authentication failed: {reason}",
        "ko": "인증 실패: {reason}",
        "ja": "認証失敗: {reason}",
        "zh": "认证失败: {reason}",
        "de": "Authentifizierung fehlgeschlagen: {reason}",
        "fr": "Échec de l'authentification : {reason}",
        "es": "Autenticación fallida: {reason}",
    },
    "token_expired": {
        "en": "Authentication token expired",
        "ko": "인증 토큰이 만료되었습니다",
        "ja": "認証トークンが期限切れです",
        "zh": "认证令牌已过期",
        "de": "Authentifizierungstoken abgelaufen",
        "fr": "Jeton d'authentification expiré",
        "es": "Token de autenticación expirado",
    },
    "insufficient_permissions": {
        "en": "Insufficient permissions for this operation",
        "ko": "이 작업에 대한 권한이 부족합니다",
        "ja": "この操作に対する権限が不足しています",
        "zh": "此操作权限不足",
        "de": "Unzureichende Berechtigungen für diese Operation",
        "fr": "Permissions insuffisantes pour cette opération",
        "es": "Permisos insuficientes para esta operación",
    },

    # ── Error ───────────────────────────────────────────────────────────
    "internal_error": {
        "en": "Internal server error",
        "ko": "내부 서버 오류",
        "ja": "内部サーバーエラー",
        "zh": "内部服务器错误",
        "de": "Interner Serverfehler",
        "fr": "Erreur interne du serveur",
        "es": "Error interno del servidor",
    },
    "rate_limit_exceeded": {
        "en": "Rate limit exceeded. Try again in {seconds} seconds",
        "ko": "요청 한도 초과. {seconds}초 후에 다시 시도하세요",
        "ja": "レート制限超過。{seconds}秒後に再試行してください",
        "zh": "请求频率超限。请在{seconds}秒后重试",
        "de": "Ratenlimit überschritten. Versuchen Sie es in {seconds} Sekunden erneut",
        "fr": "Limite de requêtes dépassée. Réessayez dans {seconds} secondes",
        "es": "Límite de solicitudes excedido. Intente de nuevo en {seconds} segundos",
    },
    "service_unavailable": {
        "en": "Service temporarily unavailable",
        "ko": "서비스를 일시적으로 사용할 수 없습니다",
        "ja": "サービスが一時的に利用できません",
        "zh": "服务暂时不可用",
        "de": "Dienst vorübergehend nicht verfügbar",
        "fr": "Service temporairement indisponible",
        "es": "Servicio temporalmente no disponible",
    },
    "invalid_request": {
        "en": "Invalid request: {detail}",
        "ko": "잘못된 요청: {detail}",
        "ja": "無効なリクエスト: {detail}",
        "zh": "无效请求: {detail}",
        "de": "Ungültige Anfrage: {detail}",
        "fr": "Requête invalide : {detail}",
        "es": "Solicitud inválida: {detail}",
    },

    # ── CLI ─────────────────────────────────────────────────────────────
    "cli_help": {
        "en": "Q-Bridge Gateway Agent — Quantum job relay server",
        "ko": "Q-Bridge 게이트웨이 에이전트 — 양자 작업 중계 서버",
        "ja": "Q-Bridge ゲートウェイエージェント — 量子ジョブ中継サーバー",
        "zh": "Q-Bridge 网关代理 — 量子作业中继服务器",
        "de": "Q-Bridge Gateway-Agent — Quanten-Job-Relay-Server",
        "fr": "Agent Passerelle Q-Bridge — Serveur relais de tâches quantiques",
        "es": "Agente de Puerta de Enlace Q-Bridge — Servidor de retransmisión de trabajos cuánticos",
    },
    "cli_version": {
        "en": "Version {version}",
        "ko": "버전 {version}",
        "ja": "バージョン {version}",
        "zh": "版本 {version}",
        "de": "Version {version}",
        "fr": "Version {version}",
        "es": "Versión {version}",
    },
    "cli_port_help": {
        "en": "Port to listen on (default: 8003)",
        "ko": "수신 포트 (기본값: 8003)",
        "ja": "リッスンポート (デフォルト: 8003)",
        "zh": "监听端口 (默认: 8003)",
        "de": "Lauschport (Standard: 8003)",
        "fr": "Port d'écoute (par défaut : 8003)",
        "es": "Puerto de escucha (predeterminado: 8003)",
    },
    "cli_host_help": {
        "en": "Host to bind to (default: 0.0.0.0)",
        "ko": "바인드할 호스트 (기본값: 0.0.0.0)",
        "ja": "バインドホスト (デフォルト: 0.0.0.0)",
        "zh": "绑定主机 (默认: 0.0.0.0)",
        "de": "Zu bindender Host (Standard: 0.0.0.0)",
        "fr": "Hôte à lier (par défaut : 0.0.0.0)",
        "es": "Host a vincular (predeterminado: 0.0.0.0)",
    },

    # ── Status ──────────────────────────────────────────────────────────
    "health_ok": {
        "en": "Service healthy",
        "ko": "서비스 정상",
        "ja": "サービス正常",
        "zh": "服务正常",
        "de": "Dienst gesund",
        "fr": "Service opérationnel",
        "es": "Servicio saludable",
    },
    "health_degraded": {
        "en": "Service degraded: {reason}",
        "ko": "서비스 성능 저하: {reason}",
        "ja": "サービス低下: {reason}",
        "zh": "服务降级: {reason}",
        "de": "Dienst beeinträchtigt: {reason}",
        "fr": "Service dégradé : {reason}",
        "es": "Servicio degradado: {reason}",
    },
    "uptime": {
        "en": "Uptime: {hours}h {minutes}m",
        "ko": "가동 시간: {hours}시간 {minutes}분",
        "ja": "稼働時間: {hours}時間{minutes}分",
        "zh": "运行时间: {hours}小时{minutes}分钟",
        "de": "Betriebszeit: {hours}h {minutes}m",
        "fr": "Temps de fonctionnement : {hours}h {minutes}m",
        "es": "Tiempo de actividad: {hours}h {minutes}m",
    },
    "active_connections": {
        "en": "{count} active connection(s)",
        "ko": "활성 연결 {count}개",
        "ja": "アクティブ接続 {count}件",
        "zh": "{count}个活跃连接",
        "de": "{count} aktive Verbindung(en)",
        "fr": "{count} connexion(s) active(s)",
        "es": "{count} conexión(es) activa(s)",
    },
    "jobs_processed": {
        "en": "{count} jobs processed",
        "ko": "처리된 작업 {count}개",
        "ja": "処理済みジョブ {count}件",
        "zh": "已处理{count}个作业",
        "de": "{count} Aufträge verarbeitet",
        "fr": "{count} tâches traitées",
        "es": "{count} trabajos procesados",
    },
}


def get_translation(key: str, lang: Optional[str] = None, **kwargs: object) -> str:
    """
    Get a translated string by key.

    Falls back in 3 tiers:
      1. Requested language
      2. English (DEFAULT_LANGUAGE)
      3. The key itself (if key not found)

    Args:
        key: Translation key (e.g., "server_starting")
        lang: Language code (e.g., "ko"). Defaults to DEFAULT_LANGUAGE.
        **kwargs: Format parameters (e.g., port=8003)

    Returns:
        Formatted translated string

    Example:
        >>> get_translation("server_starting", "ko", port=8003)
        '게이트웨이 서버가 포트 8003에서 시작합니다'
    """
    if lang is None:
        lang = DEFAULT_LANGUAGE

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    entry = translations.get(key)
    if entry is None:
        return key

    # Tier 1: requested language
    text = entry.get(lang)
    # Tier 2: English fallback
    if text is None:
        text = entry.get(DEFAULT_LANGUAGE, key)

    # Apply format parameters
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass  # Return unformatted if params don't match

    return text


def get_supported_languages() -> list[str]:
    """Return list of supported language codes."""
    return list(SUPPORTED_LANGUAGES)


def get_all_keys() -> list[str]:
    """Return list of all translation keys."""
    return list(translations.keys())
