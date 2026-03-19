export async function analyzeVideo() {
  const res = await fetch("http://localhost:8000/analyze", {
    method: "POST"
  })

  const data = await res.json()
  return data
}
