import { useState, useEffect } from "react";
import { triageAPI } from "../api/client";

export const useTriageReports = () => {
  const [reports, setReports] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setIsLoading(true);
        const response = await triageAPI.getReports();
        setReports(response.data);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch history:", err);
        setError(err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchHistory();
  }, []);

  return { reports, isLoading, error };
};
