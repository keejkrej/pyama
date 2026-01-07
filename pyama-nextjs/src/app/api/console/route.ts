export async function POST() {
  const req = await fetch('http://localhost:11434/api/tags');
  const data = await req.json();
  console.log('Ollama models:', data);
  
  return Response.json(data);
}
