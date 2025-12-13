"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface BackendStatusProps {
  apiBase?: string;
}

export function BackendStatus({
  apiBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
}: BackendStatusProps) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        // Remove trailing slash if present and append health check endpoint
        // Assuming standard endpoint structure, but usually root or specific health endpoint
        // For now we'll try to fetch the features endpoint as a proxy for health if no dedicated health endpoint exists,
        // or just the root API. Let's try a lightweight endpoint.
        // Actually, let's try the root of the backend first.
        const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/processing/features`, {
            method: "HEAD", // Lightweight check if supported, otherwise GET
        });
        
        // Fallback to GET if HEAD fails (405 Method Not Allowed)
        if (response.status === 405) {
             await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/processing/features`);
        }
        
        setIsOnline(true);
      } catch (error) {
        setIsOnline(false);
      }
    };

    // Initial check
    checkHealth();

    // Poll every 30 seconds
    const interval = setInterval(checkHealth, 30000);

    return () => clearInterval(interval);
  }, [apiBase]);

  if (isOnline === null) return null; // Loading state

  return (
    <div className="flex items-center gap-2 text-xs">
      <div
        className={cn(
          "h-2 w-2 rounded-full",
          isOnline ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]"
        )}
      />
      <span className={cn("font-medium", isOnline ? "text-emerald-500" : "text-red-500")}>
        {isOnline ? "Backend Online" : "Backend Offline"}
      </span>
    </div>
  );
}
