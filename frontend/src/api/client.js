import axios from "axios";

const client = axios.create({
  baseURL: "http://localhost:8000/api/v3",
  headers: {
    "Content-Type": "application/json",
  },
});

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
};

export default client;
