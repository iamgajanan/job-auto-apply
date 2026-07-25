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
    <main className="min-h-screen flex items-center justify-center">
      <div className="border rounded-xl p-10 space-y-4">
        <h1 className="text-3xl font-bold">
          Job Auto Apply
        </h1>

        <pre>
          {JSON.stringify(health, null, 2)}
        </pre>
      </div>
    </main>
  );
}