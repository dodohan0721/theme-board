"""Fixed reporting universes, separate from user-adjustable board filters."""
SECTORS = [
 ("XLE","에너지",["XOM","CVX","COP"],"미국 에너지 원유 뉴욕증시"),
 ("XLU","유틸리티",["VST","CEG","NEE"],"미국 유틸리티 전력 증시"),
 ("XLK","기술",["MSFT","NVDA","AAPL"],"미국 기술주 반도체 뉴욕증시"),
 ("XLV","헬스케어",["LLY","UNH","JNJ"],"미국 헬스케어 제약 뉴욕증시"),
 ("XLF","금융",["JPM","BAC","GS"],"미국 은행 금융주 뉴욕증시"),
 ("XLB","소재",["LIN","SHW","FCX"],"미국 소재주 뉴욕증시"),
 ("XLY","경기소비재",["AMZN","TSLA","HD"],"미국 소비재 테슬라 아마존 증시"),
 ("XLP","필수소비재",["WMT","PG","COST"],"미국 필수소비재 증시"),
 ("XLI","산업재",["GE","CAT","RTX"],"미국 산업재 방산 증시"),
 ("XLRE","부동산",["PLD","AMT","EQIX"],"미국 부동산 리츠 증시"),
 ("XLC","커뮤니케이션",["META","GOOGL","NFLX"],"미국 메타 구글 통신서비스 증시"),
]
THEMES = [
 {"id":"semiconductor","name":"반도체","stocks":["NVDA","AMD","AVGO","TSM","MU","INTC"],"query":"미국 반도체 엔비디아 인텔 증시","kr":[["005930","삼성전자"],["000660","SK하이닉스"]],"connection":"메모리·시스템 반도체 산업의 실적과 수요를 함께 확인합니다."},
 {"id":"crypto-related","name":"스테이블코인·크립토","stocks":["COIN","CRCL","MSTR","HOOD"],"query":"코인베이스 서클 비트코인 미국 주가","kr":[],"connection":"미국 가상자산 관련주와 실제 코인 시세는 별도로 확인합니다."},
 {"id":"humanoid","name":"휴머노이드 로봇","stocks":["TSLA","RR","SERV"],"query":"테슬라 휴머노이드 로봇 주가","kr":[["277810","레인보우로보틱스"],["454910","두산로보틱스"]],"connection":"로봇 개발·상용화 소식과 국내 로봇 기업의 실제 사업 연관성을 확인합니다."},
 {"id":"quantum","name":"양자컴퓨팅","stocks":["IONQ","RGTI","QBTS","QUBT"],"query":"양자컴퓨팅 아이온큐 리게티 주가","kr":[],"connection":"양자 기술의 상용화·계약 소식을 확인합니다. 국내 연결 기업은 근거 확보 후 표시합니다."},
 {"id":"nuclear-energy","name":"에너지·원전","stocks":["SMR","OKLO","NNE","CEG","XOM","CVX"],"query":"미국 원전 SMR 오클로 에너지 주가","kr":[["034020","두산에너빌리티"],["052690","한전기술"]],"connection":"원전 프로젝트·정책 변화와 국내 기업의 참여 여부를 함께 확인합니다."},
 {"id":"power-grid","name":"변압기·전선","stocks":["GEV","ETN","PWR","HUBB"],"query":"미국 전력 인프라 변압기 이튼 주가","kr":[["267260","HD현대일렉트릭"],["298040","효성중공업"],["010120","LS ELECTRIC"]],"connection":"송배전 설비 수요와 국내 전력기기 기업의 수주·실적을 확인합니다."},
 {"id":"solar","name":"태양광","stocks":["ENPH","SEDG","FSLR","CSIQ"],"query":"미국 태양광 퍼스트솔라 엔페이즈 주가","kr":[["009830","한화솔루션"]],"connection":"미국 태양광 정책과 국내 기업의 미국 생산·판매 사업을 함께 확인합니다."},
 {"id":"optical","name":"광통신","stocks":["LITE","COHR","CIEN","AAOI"],"query":"루멘텀 코히런트 광통신 주가","kr":[["069540","빛과전자"],["138080","오이솔루션"]],"connection":"데이터센터 광통신 수요와 국내 업체의 제품·고객 연결을 확인합니다."},
 {"id":"defense","name":"방산","stocks":["LMT","RTX","NOC","AVAV","PLTR"],"query":"미국 방산 록히드마틴 주가","kr":[["012450","한화에어로스페이스"],["079550","LIG넥스원"],["064350","현대로템"]],"connection":"방위 예산·수주 소식과 국내 방산 기업의 계약 공시를 확인합니다."},
]
NAMES={"NVDA":"엔비디아","AMD":"AMD","AVGO":"브로드컴","TSM":"TSMC","MU":"마이크론","INTC":"인텔","COIN":"코인베이스","CRCL":"서클","MSTR":"스트래티지","HOOD":"로빈후드","TSLA":"테슬라","RR":"리치테크 로보틱스","SERV":"서브 로보틱스","IONQ":"아이온큐","RGTI":"리게티","QBTS":"디웨이브","QUBT":"퀀텀 컴퓨팅","SMR":"뉴스케일파워","OKLO":"오클로","NNE":"나노 뉴클리어","CEG":"콘스텔레이션 에너지","XOM":"엑슨모빌","CVX":"셰브런","GEV":"GE 버노바","ETN":"이튼","PWR":"퀀타 서비스","HUBB":"허벨","ENPH":"엔페이즈","SEDG":"솔라엣지","FSLR":"퍼스트솔라","CSIQ":"캐나디안솔라","LITE":"루멘텀","COHR":"코히런트","CIEN":"시에나","AAOI":"어플라이드 옵토일렉트로닉스","LMT":"록히드마틴","RTX":"RTX","NOC":"노스롭그루먼","AVAV":"에어로바이런먼트","PLTR":"팔란티어"}
