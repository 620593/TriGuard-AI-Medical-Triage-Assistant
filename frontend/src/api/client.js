import axios from "axios";

const client = axios.create({
  baseURL: "http://localhost:8000/api/v3",
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      "[API Error] intercepted:",
      error.response?.data || error.message,
    );
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export const authAPI = {
  login: (data) => client.post("/auth/login", data),
  register: (data) => client.post("/auth/register", data),
};

export const triageAPI = {
  // Text triage
  triage: (data) => {
    const user = JSON.parse(localStorage.getItem("user"));
    if (user?.user_id) data.user_id = user.user_id;
    return client.post("/triage", data);
  },

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
  getSessions: () => client.get("/sessions"),
  getReports: () => client.get("/reports"),
  deleteReport: (reportId) => client.delete(`/reports/${reportId}`),

  // Static Resource Helpers
  getStaticAudioUrl: (filename) =>
    filename ? `http://localhost:8000/static/audio/${filename}` : null,
  getStaticNutritionUrl: (filename) =>
    filename ? `http://localhost:8000/static/nutrition/${filename}` : null,
};

export default client;
