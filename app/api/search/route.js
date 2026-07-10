import { NextResponse } from 'next/server';
import YTMusic from 'ytmusic-api';

const BLACKLIST_PATTERNS = [
  /\bgameplay\b/i, /\blet'?s play\b/i, /\bplaythrough\b/i, /\bwalkthrough\b/i,
  /\bspeedrun\b/i, /\bno commentary\b/i, /\bgaming session\b/i, /\bstream highlight\b/i,
  /\btwitch (highlight|clip)\b/i, /\branked (game|match|gameplay)\b/i,
  /\b(fps|moba|pvp|pve) gameplay\b/i, /\bbattle royale gameplay\b/i,
  /\breacts? to\b/i, /\breacting to\b/i, /\bunboxing\b/i,
  /\b(phone|laptop|gpu|cpu|pc) (review|build)\b/i,
  /\bdaily vlog\b/i, /\bweekly vlog\b/i, /\b#vlog\b/i,
];

const WHITELIST_PATTERNS = [
  /\bost\b/i, /\boriginal soundtrack\b/i, /\bsoundtrack\b/i, /\bgame (music|ost|bgm|theme)\b/i,
  /\bbgm\b/i, /\blyrics?\b/i, /\bcover\b/i, /\bacoustic\b/i, /\bpiano\b/i, /\borchestral\b/i,
  /\bremix\b/i, /\bfeat\b/i, /\bft\.\b/i, /\bprod\.\b/i, /\baudio\b/i,
  /\bdubbing\b/i, /\bdub\b/i, /\bsub indo\b/i, /\bkaraoke\b/i,
];

function isMusicContent(title) {
  const tl = (title || '').toLowerCase();
  if (WHITELIST_PATTERNS.some(p => p.test(tl))) return true;
  if (BLACKLIST_PATTERNS.some(p => p.test(tl))) return false;
  return true;
}

let _ytmusicClient = null;
async function getClient() {
  if (!_ytmusicClient) {
    _ytmusicClient = new YTMusic();
    await _ytmusicClient.initialize();
  }
  return _ytmusicClient;
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get('q');
  const max = searchParams.get('max') || 12;

  if (!q) return NextResponse.json({ error: 'Query required' }, { status: 400 });

  try {
    const ytmusic = await getClient();
    const results = await ytmusic.searchSongs(q);

    const tracks = results
      .filter(v => v.videoId)
      .filter(v => isMusicContent(v.name))
      .slice(0, parseInt(max))
      .map(v => ({
        id: v.videoId,
        title: v.name || '',
        channel: v.artist?.name || (Array.isArray(v.artists) ? v.artists.map(a => a.name).join(', ') : '') || '',
        thumb: v.thumbnails?.[v.thumbnails.length - 1]?.url || `https://i.ytimg.com/vi/${v.videoId}/mqdefault.jpg`,
      }));

    return NextResponse.json(tracks, {
      headers: { 'Cache-Control': 's-maxage=60, stale-while-revalidate' },
    });
  } catch (e) {
    const key = process.env.YOUTUBE_API_KEY;
    if (key) {
      try {
        const url = `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${encodeURIComponent(q)}&type=video&maxResults=${max}&key=${key}`;
        const r = await fetch(url);
        if (r.ok) {
          const data = await r.json();
          if (data.items?.length) {
            return NextResponse.json(
              data.items
                .filter(item => isMusicContent(item.snippet.title))
                .map(item => ({
                  id: item.id.videoId,
                  title: item.snippet.title,
                  channel: item.snippet.channelTitle,
                  thumb: item.snippet.thumbnails?.medium?.url || `https://i.ytimg.com/vi/${item.id.videoId}/mqdefault.jpg`,
                }))
            );
          }
        }
      } catch {}
    }
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
