import axios from "axios";

const client = axios.create({
  baseURL: "http://localhost:8000/api/v3",
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      "[API Error] intercepted:",
      error.response?.data || error.message,
    );
    return Promise.reject(error);
  },
);

export const triageAPI = {
  // Text triage
  triage: (data) => client.post("/triage", data),

  // Voice triage
  voice: (formData) =>
    client.post("/voice", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  // OCR Document analysis
  image: (formData) =>
    client.post("/image", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  // X-ray analysis
  xray: (formData) =>
    client.post("/xray", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  // Health check
  getHealth: () => client.get("/health"),

  // History & Reports
  getSessions: (userId = "anonymous") =>
    client.get("/sessions", { headers: { "X-User-Id": userId } }),
  getReports: (userId = "anonymous") =>
    client.get("/reports", { headers: { "X-User-Id": userId } }),
  deleteReport: (reportId, userId = "anonymous") =>
    client.delete(`/reports/${reportId}`, { headers: { "X-User-Id": userId } }),

  // Static Resource Helpers
  getStaticAudioUrl: (filename) =>
    filename ? `http://localhost:8000/static/audio/${filename}` : null,
  getStaticNutritionUrl: (filename) =>
    filename ? `http://localhost:8000/static/nutrition/${filename}` : null,
};

export default client;
