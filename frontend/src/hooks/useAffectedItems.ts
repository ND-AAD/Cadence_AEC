import { useState, useEffect } from "react";
import { getAffectedItems } from "@/api/dashboard";
import type { AffectedItemsResponse } from "@/types/dashboard";

export function useAffectedItems(projectId: string | null) {
  const [data, setData] = useState<AffectedItemsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setData(null);
      return;
    }
    setLoading(true);
    getAffectedItems(projectId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId]);

  return { affectedItems: data, loading };
}
