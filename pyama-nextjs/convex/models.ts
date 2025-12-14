import { action } from "./_generated/server";

export const list = action({
  args: {},
  handler: async (): Promise<string[]> => {
    const baseUrl = process.env.OPENAI_BASE_URL;
    const apiKey = process.env.OPENAI_API_KEY;

    if (!baseUrl) {
      console.error("OPENAI_BASE_URL not configured");
      return [];
    }

    try {
      const response = await fetch(`${baseUrl}/models`, {
        headers: {
          Authorization: `Bearer ${apiKey ?? ""}`,
        },
      });

      if (!response.ok) {
        console.error("Failed to fetch models:", response.statusText);
        return [];
      }

      const data = await response.json();
      const models: string[] = data.data?.map((m: { id: string }) => m.id) ?? [];
      return models;
    } catch (error) {
      console.error("Error fetching models:", error);
      return [];
    }
  },
});
