console.log("clinic_data.js loaded");

const clinics = [
  // 산부인과
  { id: 8, name: "봄빛 병원", type: "산부인과", typeClass: "type-ob", logo: "bombit.jpg" },
  { id: 25, name: "이쁜여성의원", type: "산부인과", typeClass: "type-ob", logo: "이쁜여성의원.jpg" },
  { id: 26, name: "여노피 <br>산부인과", type: "산부인과", typeClass: "type-ob", logo: "여노피.jpg" },

  // 성형외과
  { id: 9, name: "원트 성형외과", type: "성형외과", typeClass: "type-ps", logo: "원트.jpg" },
  { id: 7, name: "윈느 성형외과", type: "성형외과", typeClass: "type-ps", logo: "윈느.jpg" },
  { id: 12, name: "신상 성형외과", type: "성형외과", typeClass: "type-ps", logo: "신상.jpg" },
  { id: 10, name: "밸런스랩 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "밸런스랩.jpg" },
  { id: 19, name: "밸런스랩 <br> A&A", type: "성형외과", typeClass: "type-ps", logo: "A&A.jpg" },
  { id: 11, name: "히트 성형외과", type: "성형외과", typeClass: "type-ps", logo: "히트.jpg" },
  { id: 15, name: "다름 성형외과", type: "성형외과", typeClass: "type-ps", logo: "다름.jpg" },
  { id: 14, name: "지힐링스퀘어", type: "성형외과", typeClass: "type-ps", logo: "지힐링.jpg" },
  { id: 16, name: "아우어 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "아우어.jpg" },
  { id: 17, name: "강남12의원", type: "성형외과", typeClass: "type-ps", logo: "강남12.jpg" },
  { id: 18, name: "프리마 <br> 성형외과", type: "성형외과", typeClass: "type-ps", logo: "프리마.jpg" },
  { id: 33, name: "서진 성형외과", type: "성형외과", typeClass: "type-ps", logo: "서진.jpg" },
  { id: 21, name: "라라 성형외과", type: "성형외과", typeClass: "type-ps", logo: "라라.jpg" },

  // 피부과
  { id: 34, name: "사치바이오", type: "피부과", typeClass: "type-derma", logo: "사치바이오.jpg" },
  { id: 23, name: "PHD피부과", type: "피부과", typeClass: "type-derma", logo: "PHD.jpg" },
  { id: 24, name: "리프톤 피부과", type: "피부과", typeClass: "type-derma", logo: "리프톤.jpg" },
  { id: 31, name: "용닥터의원", type: "피부과", typeClass: "type-derma", logo: "용닥터.jpg" },
];

// 🔥 전역 노출
window.clinics = clinics;