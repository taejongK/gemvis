# Gemvis 데모 영상 시나리오 (5분)

> **제작 목적**: Kaggle Gemma 4 Good Hackathon 제출 영상  
> **타겟 관객**: 심사위원 (기술적 깊이 + 사회적 임팩트 평가)  
> **핵심 메시지**: "정보 불평등 해소 + 프라이버시 보장 + 기술적 혁신"

---

## 📐 전체 구조 (3막 구조 + Hook & CTA)

```
Hook (30초)       → 문제 공감 유도
Act 1 (1분)       → 문제의 심각성 (통계 + 실제 사례)
Act 2 (2분 30초)  → 해결책 시연 (라이브 데모 2개)
Act 3 (1분)       → 기술 설명 + 사회적 임팩트
```

**총 5분** (4분 50초 목표, 10초 버퍼)

---

## 🎬 Scene-by-Scene Breakdown

### **HOOK: "잃어버린 기억" (0:00 ~ 0:30)**

#### Visual

- **Screen Record**: Downloads 폴더 스크롤 (100+ 파일, 무질서)
- **Text Overlay**: "2026-03-15_meeting.pdf"를 찾는 Finder/Explorer 검색 화면
- **Frustration montage**: Ctrl+F 반복, 잘못된 파일 클릭, 닫기 반복

#### Audio (Voice Over)

> **[침착하지만 공감 가는 톤]**  
> "여러분의 Downloads 폴더를 보여드립니다."  
> (3초 pause)  
> "우리는 정보를 저장하지 못해서 잃어버리는 것이 아닙니다.  
> 너무 많이 저장해서, 다시 찾지 못할 뿐입니다."

#### Text Overlay

```
평균 사용자는 파일 찾는데 주당 2시간 소비
연간 100시간 = $5,000 생산성 손실
```

**⏱️ 타이밍**: 0:00 ~ 0:30 (30초)

---

### **ACT 1: 문제의 본질 (0:30 ~ 1:30)**

#### Scene 1.1: 정보 폭발 (0:30 ~ 0:50)

**Visual**:

- 애니메이션: 파일 아이콘이 화면에 기하급수적으로 증가
- 그래프: "Data Creation vs Human Cognitive Capacity" (exponential vs flat)

**Audio (VO)**:

> "AI가 발전하면서 우리가 다뤄야 할 정보는 기하급수적으로 증가하고 있습니다.  
> 하지만 인간의 인지 능력은 변하지 않았습니다."

**Text Overlay**:

```
📊 22.5% of workers cite "information overload" as #1 stressor
    (Meyer et al., 2021, Frontiers in Psychology)
```

#### Scene 1.2: 기존 해결책의 한계 (0:50 ~ 1:10)

**Visual**: Split screen

- **왼쪽**: 클라우드 AI (ChatGPT 로고) → ❌ 표시
- **오른쪽**: 폴더 정리 (복잡한 계층 구조) → ❌ 표시

**Audio (VO)**:

> "기존 해결책은 두 가지입니다.  
> 클라우드 AI: 강력하지만 프라이버시를 포기해야 합니다.  
> 수동 정리: 안전하지만 게으르고 귀찮은 일이죠."

#### Scene 1.3: 전환점 (1:10 ~ 1:30)

**Visual**:

- Gemma 4 로고 등장 (빛나는 효과)
- "2GB" 텍스트 강조
- 노트북 위에 Gemvis 로고 오버레이

**Audio (VO)**:

> **[톤 변화: 희망적]**  
> "Gemma 4 E2B-it이 게임의 룰을 바꿨습니다.  
> 단 2GB. 소형 노트북에서도 돌아가는 첫 번째 진짜 휴대용 LLM입니다."

**Text Overlay**:

```
Gemvis = Gemma + Jarvis + Vision
Privacy-First On-Device Knowledge Graph Assistant
```

**⏱️ 타이밍**: 0:30 ~ 1:30 (1분)

---

### **ACT 2: 해결책 시연 (1:30 ~ 4:00)**

#### Scene 2.1: 데모 준비 (1:30 ~ 1:40)

**Visual**: Gemvis 메인 화면 (Dashboard)

- 파일 100개 이미 분석 완료 상태
- 통계 대시보드 (카테고리별 분포)

**Audio (VO)**:

> "Gemvis를 소개합니다. 사용법은 간단합니다.  
> 원하는 폴더를 지정하면, 나머지는 알아서 합니다."

#### Scene 2.2: **라이브 데모 #1 - "잃어버린 파일 찾기"** (1:40 ~ 3:00)

##### 2.2.1: 검색 실행 (1:40 ~ 1:50)

**Visual**:

- `Ctrl+K` 누름 → Spotlight 검색창 오픈 (전체 화면 오버레이)
- 타이핑 애니메이션: "지난달 김과장이랑 논의한 프로젝트 파일"

**Audio (VO)**:

> "지난달 김과장과 논의한 프로젝트 파일을 찾아볼까요?  
> Ctrl+K를 누르고, 자연어로 질문합니다."

##### 2.2.2: 결과 표시 (1:50 ~ 2:20)

**Visual**:

- AI 답변 출력 (타이핑 효과)

```
"강남역 근처 식당에서 논의하신 Gemvis 프로젝트 관련 파일이에요.
관련 파일 3개를 찾았습니다:
1. meeting_notes_2026-03-15.pdf (회의록)
2. IMG_1234.jpg (회의 화이트보드 사진)
3. voice_memo_march15.m4a (아이디어 녹음)"
```

- 파일 목록 하이라이트
- 커서가 첫 번째 파일 호버

**Audio (VO)**:

> **[놀라운 톤]**  
> "3초 만에 찾았습니다. 단순 키워드 검색이 아닙니다.  
> Gemvis는 파일 간의 관계를 이해합니다."

##### 2.2.3: 그래프 뷰 전환 (2:20 ~ 3:00)

**Visual**:

- `Ctrl+Alt+V` 누름
- 화면 전환: Graph View
- 노드 강조 애니메이션:
  - **중심**: "Gemvis 프로젝트" (주황색 노드)
  - **연결**: "김과장" (인물 노드) ↔ "강남역 식당" (장소 노드) ↔ 3개 파일 노드
  - 관계 경로 하이라이트 (빛나는 선)

**Audio (VO)**:

> "이것이 Gemvis의 핵심입니다. 지식그래프입니다.  
> 파일, 사람, 장소, 프로젝트가 모두 연결되어 있습니다.  
> 단순히 찾는 것이 아니라, 이해하는 것입니다."

**Text Overlay** (우측 하단):

```
✅ Hybrid Search: SPARQL + Embeddings + LLM
✅ Knowledge Graph: Auto-built from file contents
✅ 100% Local: Zero cloud, zero surveillance
```

**⏱️ 타이밍**: 1:40 ~ 3:00 (1분 20초)

---

#### Scene 2.3: **라이브 데모 #2 - "자동 정리의 마법"** (3:00 ~ 3:50)

##### 2.3.1: 파일 추가 (3:00 ~ 3:10)

**Visual**:

- Split screen:
  - **왼쪽**: 파일 탐색기 (새 PDF 파일 `GNN_survey_2026.pdf`를 Downloads 폴더에 드래그)
  - **오른쪽**: Gemvis Dashboard (상태 변화 모니터링)

**Audio (VO)**:

> "이제 새 파일을 추가해보겠습니다.  
> 그냥 폴더에 드롭하면 됩니다."

##### 2.3.2: 실시간 분석 (3:10 ~ 3:30)

**Visual**:

- Dashboard에 알림 팝업:

```
🔄 분석 중... GNN_survey_2026.pdf
📊 GemInsight 추출 중 (5초 경과)
```

- 진행 바 애니메이션
- 5초 후 완료:

```
✅ 분석 완료!

파일: Graph Neural Networks Survey
주제: 머신러닝, 그래프 이론
관련 프로젝트: Gemvis (지식그래프 사용)
제안: '프로젝트/Gemvis/참고자료' 폴더에 정리할까요?

[승인] [거부] [다른 위치]
```

**Audio (VO)**:

> "5초 만에 분석이 끝났습니다.  
> Gemvis가 내용을 읽고, 주제를 파악하고, 관련 프로젝트를 찾아냅니다."

##### 2.3.3: 그래프 업데이트 (3:30 ~ 3:50)

**Visual**:

- **승인** 버튼 클릭
- 화면 전환: Graph View
- 애니메이션:
  - 새 노드 "GNN_survey_2026.pdf" 생성 (빛나며 등장)
  - 자동으로 "Gemvis 프로젝트" 노드와 연결 (선이 그려짐)
  - "머신러닝" 태그 노드와도 연결
  - 그래프가 유기적으로 재배치 (force-directed layout)

**Audio (VO)**:

> "그리고 지식그래프가 자동으로 확장됩니다.  
> 사용자는 아무것도 하지 않았습니다.  
> Gemvis가 모든 것을 기억하고, 연결합니다."

**Text Overlay** (중앙 하단):

```
제로 사용자 노력
자동 엔티티 추출 → 자동 관계 연결 → 자동 그래프 확장
```

**⏱️ 타이밍**: 3:00 ~ 3:50 (50초)

---

### **ACT 3: 기술 깊이 + 사회적 임팩트 (3:50 ~ 4:50)**

#### Scene 3.1: 기술 설명 (3:50 ~ 4:20)

**Visual**:

- 아키텍처 다이어그램 애니메이션:

```
User File → Watchdog → Gemma 4 E2B-it (Local LLM)
                            ↓
                       GemInsight Extraction
                            ↓
            Knowledge Graph (RDF/Turtle + SPARQL)
                   +
            Embeddings (sentence-transformers)
                            ↓
                    Hybrid Search Engine
```

- 각 컴포넌트가 순서대로 하이라이트

**Audio (VO)**:

> "Gemvis는 단순한 도구가 아닙니다.  
> Gemma 4 로컬 LLM, 지식그래프, 임베딩 검색, 파일시스템 통합.  
> 네 가지 기술이 완전히 통합된 복합 시스템입니다."

**Text Overlay**:

```
✅ Gemma 4 E2B-it: On-device LLM (~2GB)
✅ Knowledge Graph: rdflib + SPARQL
✅ Embeddings: sentence-transformers (local)
✅ File Watching: Real-time monitoring
```

#### Scene 3.2: 사회적 임팩트 (4:20 ~ 4:50)

**Visual**:

- 3개 아이콘 등장 (좌→우):
  - 🌍 지구본 (디지털 접근성)
  - 🔒 자물쇠 (프라이버시)
  - 💰 동전 (경제적 평등)

**Audio (VO)**:

> "Gemvis는 세 가지 불평등을 동시에 해결합니다.  
>  
> 하나. 인터넷이 없어도 AI를 사용할 수 있습니다.  
> 둘. 구독료가 없습니다. 누구나 평등하게 접근합니다.  
> 셋. 데이터 주권을 보장합니다. 당신의 기억은 당신의 것입니다."

**Text Overlay** (중앙 큰 글씨):

```
Digital Equity for All

🌐 Offline AI Access
💸 Zero Subscription Cost
🔒 Data Sovereignty
```

**⏱️ 타이밍**: 3:50 ~ 4:50 (1분)

---

### **CLOSING: Call to Action (4:50 ~ 5:00)**

#### Visual

- Gemvis 로고 + GitHub/Kaggle 링크
- QR 코드 (레포지토리)

#### Audio (VO)

> **[자신감 있고 명확한 톤]**  
> "Gemvis.  
> 디지털 세계에서 잃어버린 기억을 되찾아주는,  
> 프라이버시를 지키는 개인 AI 비서입니다.  
>  
> Gemma 4 덕분에, 이제 클라우드 없이도 가능합니다."

**Text Overlay** (페이드 인):

```
Gemvis
Privacy-First On-Device Knowledge Graph Assistant

🔗 github.com/[your-repo]
🏆 Kaggle Gemma 4 Good Hackathon
🎯 Digital Equity & Inclusivity Track
```

**⏱️ 타이밍**: 4:50 ~ 5:00 (10초)

---

## 🎨 제작 가이드라인

### 비주얼 스타일

- **컬러 팔레트**:
  - Primary: Deep Blue (#1a365d) - 신뢰감
  - Accent: Orange (#f56565) - 에너지, 주목
  - Background: White/Light Gray (#f7fafc)
- **폰트**:
  - 제목: Montserrat Bold
  - 본문: Inter Regular
  - 코드: JetBrains Mono
- **애니메이션**:
  - 부드러운 전환 (ease-in-out, 300ms)
  - 그래프 노드 등장: Spring physics (react-spring)
  - 타이핑 효과: 50ms/char

### 오디오 스타일

- **Voice Over**:
  - 톤: 전문적이지만 친근함, 공감 가능한 목소리
  - 속도: 140 WPM (너무 빠르지 않게)
  - 감정: Hook (공감) → Act 1 (우려) → Act 2 (놀라움) → Act 3 (희망)
- **BGM**:
  - Intro: Minimal piano (사색적)
  - Demo: Uplifting electronic (에너지)
  - Closing: Inspiring orchestral (희망적)
  - Volume: -30dB (VO 방해 안 되게)

### 화면 레이아웃

- **16:9 비율** (1920x1080)
- **Safe Zone**: 중앙 80% (텍스트 오버레이)
- **Picture-in-Picture**: 데모 중 작은 웹캠 (발표자 얼굴) 우측 하단 (선택사항)

---

## 📋 제작 체크리스트

### Pre-Production

- [ ] 스크립트 최종 검토 (5분 이내 확인)
- [ ] 데모 환경 준비 (Gemvis 설치 + 테스트 데이터)
- [ ] 화면 녹화 소프트웨어 설정 (OBS Studio 권장)
- [ ] Voice Over 녹음 환경 (조용한 공간, 좋은 마이크)

### Production

- [ ] Scene별 화면 녹화 (여러 테이크 확보)
- [ ] Voice Over 녹음 (섹션별로 나눠서)
- [ ] 그래프 애니메이션 별도 렌더링 (고화질)
- [ ] B-roll 준비 (폴더 스크롤, 파일 검색 등)

### Post-Production

- [ ] 영상 편집 (Adobe Premiere / DaVinci Resolve)
- [ ] 오디오 믹싱 (VO + BGM 밸런스)
- [ ] 텍스트 오버레이 추가 (Keynote/After Effects)
- [ ] 컬러 그레이딩
- [ ] 최종 출력: MP4 (H.264, 1080p, 60fps, 10Mbps)

### Quality Check

- [ ] 타이밍 정확도 (4분 50초 ~ 5분)
- [ ] 오디오 레벨 (-6dB peak, -20dB average)
- [ ] 텍스트 가독성 (큰 화면 + 모바일)
- [ ] 데모 정확성 (모든 클릭이 의도대로)
- [ ] 자막 추가 (영어, 한국어)

---

## 🎯 성공 지표

**심사위원이 느껴야 할 것**:

1. ✅ **공감**: "나도 이 문제 겪어봤어" (Downloads 폴더)
2. ✅ **감탄**: "이렇게 해결할 수 있구나" (그래프 시각화)
3. ✅ **확신**: "실제로 쓸 수 있겠어" (즉시 배포 가능)
4. ✅ **임팩트**: "이게 정말 필요한 사람 많겠다" (20억 사용자)

**측정 가능한 목표**:

- 데모 영상 조회수: >1,000 (Kaggle 커뮤니티)
- 투표 수: Top 10 진입
- 심사위원 피드백: "기술적 깊이 + 사회적 임팩트" 언급

---


**최종 마감**: 2026-05-13 (제출 2일 전)
