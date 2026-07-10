import { NextResponse } from 'next/server';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const name = searchParams.get('name');
  if (!name) return NextResponse.json({ error: 'Artist name required' }, { status: 400 });

  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) return NextResponse.json({ error: 'API key not configured' }, { status: 500 });

  try {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        max_tokens: 300,
        messages: [
          {
            role: 'user',
            content: `Tulis bio artis musik "${name}" dalam bahasa Indonesia, 3-4 kalimat yang panjang dan natural. Ceritakan genre musiknya, gaya bermusik, hal unik yang membuat mereka berbeda, dan dampaknya terhadap pendengar. Kalau artis ini tidak terkenal, buat bio yang masuk akal berdasarkan nama dan kemungkinan genre musiknya. Jangan tulis "saya tidak tahu" atau "tidak ada info". Langsung tulis bionya saja tanpa intro atau kata pembuka.`,
          },
        ],
      }),
    });

    const data = await response.json();
    const bio = data.choices?.[0]?.message?.content || '';
    if (!bio) throw new Error('Empty response');

    return NextResponse.json(
      { bio },
      { headers: { 'Cache-Control': 's-maxage=86400, stale-while-revalidate' } }
    );
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
