"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";

export default function Home() {
  const [health, setHealth] = useState<any>();

  useEffect(() => {
    api.get("/health").then((res) => {
      setHealth(res.data);
    });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="rounded-xl border p-10">
        <h1 className="mb-6 text-3xl font-bold">
          Job Auto Apply
        </h1>

        <pre>
          {JSON.stringify(
            health,
            null,
            2
          )}
        </pre>
      </div>
    </main>
  );
}