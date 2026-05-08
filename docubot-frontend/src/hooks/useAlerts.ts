import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "../services/api";
import type { Alert } from "../types";

export function useAlerts(projectId: string, params?: { status?: string; severity?: string }) {
  return useQuery<Alert[]>({
    queryKey: ["alerts", projectId, params],
    queryFn: () => alertsApi.list(projectId, params).then((r) => r.data),
    enabled: !!projectId,
  });
}

export function useUpdateAlertStatus(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, newStatus }: { alertId: string; newStatus: string }) =>
      alertsApi.updateStatus(projectId, alertId, newStatus).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts", projectId] }),
  });
}
