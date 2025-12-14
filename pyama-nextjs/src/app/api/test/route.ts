import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const { messages } = await req.json();
  
  console.log("Test route called with:", messages?.length, "messages");
  
  // Try to fetch from OpenAI API directly
  try {
    const response = await fetch(`${process.env.OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: "llama3.1", // Use a common default model
        messages: messages.map((m: any) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.parts?.[0]?.text || "",
        })),
        stream: true,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("OpenAI API error:", response.status, errorText);
      return new Response(errorText, { status: response.status });
    }

    // Stream the response
    return new Response(response.body, {
      headers: { "Content-Type": "text/event-stream" },
    });
  } catch (error) {
    console.error("Test error:", error);
    return NextResponse.json({ error: "Test server error" }, { status: 500 });
  }
}
