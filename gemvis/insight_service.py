"""GemInsight 서비스 레이어 - 비즈니스 로직 및 데이터 접근 추상화.

이 모듈은 GemInsight의 생성, 조회, 업데이트를 관리하는 서비스 레이어입니다.
Knowledge Graph, Embeddings, EventLog 3중 저장소를 통합 관리합니다.

v2 (geminsight-develop): `raw_insight` 속성에 저장된 JSON 원본을 역직렬화해
GemInsight를 복원합니다. 구버전 노드(raw_insight 없음)는 KG 이웃 순회
fallback으로 복원합니다 — relations는 fallback 경로에서 복원 불가.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

from gemvis.insight import GemInsight, generate_insight
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.embeddings import EmbeddingStore
from gemvis.event_log import EventLog
from gemvis.schedule import WorkSchedule

logger = logging.getLogger(__name__)


class InsightService:
    """GemInsight 관리 서비스.

    GemInsight의 생성, 조회, 삭제를 담당하며, 3중 저장소(KG, Embeddings, EventLog)를
    트랜잭션처럼 일관성 있게 관리합니다.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        event_log: EventLog | None = None,
        schedule: WorkSchedule | None = None,
    ):
        self.kg = knowledge_graph
        self.event_log = event_log
        self.schedule = schedule

    def save_insight(self, insight: GemInsight, period: str = "work") -> bool:
        """GemInsight를 3곳에 동시 저장 (트랜잭션 패턴).

        Args:
            insight: 저장할 GemInsight 객체
            period: "work" 또는 "personal" (이벤트 로그용)

        Returns:
            성공 여부
        """
        if insight.error:
            logger.warning("Skipping errored insight: %s", insight.error)
            return False

        try:
            # 1. Knowledge Graph에 추가 (내부에서 Embeddings도 처리)
            self.kg.add_insight(insight)

            # 2. EventLog에 기록 (파일의 실제 수정 시간 사용)
            if self.event_log:
                from datetime import datetime
                timestamp = datetime.fromtimestamp(insight.file_mtime) if insight.file_mtime else None
                self.event_log.record("created", insight.file_path, timestamp=timestamp, period=period)

            logger.info(
                "Saved GemInsight: %s (category: %s, %d tags, %d entities)",
                Path(insight.file_path).name,
                insight.category,
                len(insight.tags),
                sum(len(v) for v in insight.entities.values()),
            )
            return True

        except Exception as e:
            logger.error("Failed to save GemInsight for %s: %s", insight.file_path, e)
            return False

    def get_insight(self, file_path: str) -> GemInsight | None:
        """파일 경로로 GemInsight 조회 (Knowledge Graph에서).

        v2 경로:
          1. file 노드의 `raw_insight` JSON을 역직렬화 → 완전 복원 (relations 포함)
          2. raw_insight가 없는 구버전 노드는 _node_to_insight() fallback
             (fallback은 relations 복원 불가)

        Args:
            file_path: 절대 경로

        Returns:
            GemInsight 객체 또는 None (존재하지 않으면)
        """
        node_id = f"file:{file_path}"
        if not self.kg.has_node(node_id):
            return None

        node_type, name = node_id.split(":", 1)
        node_uri = self.kg._node_uri(node_type, name)
        node_dict = self.kg._node_to_dict(node_uri)

        if not node_dict:
            return None

        # v2: raw_insight JSON에서 완전 복원 (relations 포함)
        raw = node_dict.get("raw_insight")
        if raw:
            try:
                return GemInsight.from_dict(json.loads(raw))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "raw_insight parse failed for %s: %s — falling back to neighbor assembly",
                    file_path, e,
                )

        # Fallback: 구버전 노드 (raw_insight 없음) — KG 이웃 순회로 재조립
        return self._node_to_insight(node_dict)

    def get_all_insights(
        self,
        limit: int = 100,
        offset: int = 0,
        category: str | None = None,
    ) -> list[GemInsight]:
        """전체 GemInsight 목록 조회.

        Args:
            limit: 최대 반환 개수
            offset: 시작 오프셋 (페이징용)
            category: 카테고리 필터 (선택)

        Returns:
            GemInsight 객체 리스트
        """
        file_nodes = self.kg.get_file_nodes()
        insights = []

        for node in file_nodes:
            # v2: raw_insight 우선, 없으면 fallback
            insight: GemInsight | None = None
            raw = node.get("raw_insight")
            if raw:
                try:
                    insight = GemInsight.from_dict(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    insight = None
            if insight is None:
                insight = self._node_to_insight(node)

            if insight:
                if category and insight.category != category:
                    continue
                insights.append(insight)

        # 페이징 적용
        return insights[offset : offset + limit]

    def count_by_category(self) -> dict[str, int]:
        """카테고리별 GemInsight 개수 집계.

        Returns:
            {category: count} 딕셔너리
        """
        insights = self.get_all_insights(limit=10000)  # 전체 조회
        counts: dict[str, int] = {}

        for insight in insights:
            counts[insight.category] = counts.get(insight.category, 0) + 1

        return counts

    def regenerate_insight(self, file_path: str) -> GemInsight | None:
        """GemInsight 재생성 (파일 재분석).

        기존 GemInsight를 삭제하고 새로 생성합니다.

        Args:
            file_path: 절대 경로

        Returns:
            새로 생성된 GemInsight 또는 None (실패 시)
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("File not found: %s", file_path)
            return None

        # 기존 노드 삭제
        node_id = f"file:{file_path}"
        if self.kg.has_node(node_id):
            self.kg.remove_node(f"file:{file_path}")
            logger.info("Removed existing GemInsight for: %s", path.name)

        # 새 GemInsight 생성
        insight = generate_insight(path)

        # 저장 (period는 현재 시간 기준으로 자동 결정)
        period = "work"
        if self.schedule:
            now = datetime.now()
            period = self.schedule.period_for(now)

        if self.save_insight(insight, period):
            return insight
        return None

    def delete_insight(self, file_path: str) -> bool:
        """GemInsight 삭제 (파일 삭제 시 호출).

        Args:
            file_path: 절대 경로

        Returns:
            성공 여부
        """
        node_id = f"file:{file_path}"
        if not self.kg.has_node(node_id):
            logger.warning("GemInsight not found: %s", file_path)
            return False

        try:
            # Knowledge Graph에서 제거 (Embeddings도 함께 제거됨)
            self.kg.remove_node(f"file:{file_path}")

            # EventLog에 삭제 기록
            if self.event_log:
                period = "work"
                if self.schedule:
                    now = datetime.now()
                    period = self.schedule.period_for(now)
                self.event_log.record("deleted", file_path, period)

            logger.info("Deleted GemInsight: %s", Path(file_path).name)
            return True

        except Exception as e:
            logger.error("Failed to delete GemInsight for %s: %s", file_path, e)
            return False

    def _node_to_insight(self, node_dict: dict) -> GemInsight | None:
        """Knowledge Graph 노드를 GemInsight 객체로 변환.

        Args:
            node_dict: KnowledgeGraph._node_to_dict() 반환값

        Returns:
            GemInsight 객체 또는 None
        """
        if node_dict.get("type") != "file":
            return None

        file_path = node_dict.get("name", "")
        if not file_path:
            return None

        # 기본 필드 + v2 state fields (skeleton-only pending 노드도 올바로 복원)
        size_raw = node_dict.get("size_bytes", "")
        try:
            size_val: int | None = int(size_raw) if size_raw else None
        except (ValueError, TypeError):
            size_val = None

        insight = GemInsight(
            file_path=file_path,
            category=node_dict.get("category", "other"),
            summary=node_dict.get("summary", ""),
            risk_level=node_dict.get("risk_level", "auto_safe"),
            analysis_status=node_dict.get("analysis_status", "completed"),
            last_analyzed_at=node_dict.get("last_analyzed_at") or None,
            added_at=node_dict.get("added_at") or None,
            size_bytes=size_val,
            error=node_dict.get("error") or None,
        )

        # Tags 수집 (tagged_with 엣지 탐색)
        node_id = node_dict["id"]
        neighbors = self.kg.get_neighbors(node_id)
        for neighbor in neighbors:
            if neighbor.get("type") == "tag":
                insight.tags.append(neighbor.get("name", ""))

        # Entities 수집 (mentions, taken_at, part_of 등 엣지 탐색)
        entity_type_map = {
            "person": "people",
            "place": "places",
            "project": "projects",
            "event": "events",
            "date": "dates",
        }

        for neighbor in neighbors:
            neighbor_type = neighbor.get("type")
            if neighbor_type in entity_type_map:
                entity_key = entity_type_map[neighbor_type]
                entity_name = neighbor.get("name", "")
                if entity_name:
                    insight.entities[entity_key].append(entity_name)

        # Relations는 현재 Knowledge Graph에서 직접 복원 어려움
        # (source/target을 모두 알아야 하는데 노드 중심 조회라 한계)
        # TODO: 필요 시 별도 쿼리로 복원

        return insight
