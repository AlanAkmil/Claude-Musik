import { NextResponse } from 'next/server';
import { YTMusic } from 'ytmusic-api';

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
  const list = searchParams.get('list');

  if (!list) return NextResponse.json({ error: 'Playlist ID required' }, { status: 400 });

  try {
    const ytmusic = await getClient();
    const playlist = await ytmusic.getPlaylist(list);

    const tracks = (playlist.videos || playlist.songs || [])
      .filter(v => v.videoId)
      .map(v => ({
        id: v.videoId,
        title: v.name || '',
        channel: v.artist?.name || (Array.isArray(v.artists) ? v.artists.map(a => a.name).join(', ') : '') || '',
        thumb: v.thumbnails?.[v.thumbnails.length - 1]?.url || `https://i.ytimg.com/vi/${v.videoId}/mqdefault.jpg`,
      }));

    if (!tracks.length) throw new Error('Playlist kosong atau tidak bisa diakses');

    return NextResponse.json(
      { title: playlist.name || 'Playlist YouTube Music', tracks },
      { headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate' } }
    );
  } catch (e) {
    try {
      const playlistUrl = `https://www.youtube.com/playlist?list=${list}`;
      const response = await fetch(playlistUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept-Language': 'en-US,en;q=0.9',
        },
      });
      const html = await response.text();
      const match =
        html.match(/var ytInitialData\s*=\s*({.+?});<\/script>/s) ||
        html.match(/ytInitialData\s*=\s*({.+?});\s*(?:var|window|<\/script>)/s);
      if (!match) throw new Error('Tidak bisa parse playlist YouTube');
      const data = JSON.parse(match[1]);
      const contents =
        data?.contents?.twoColumnBrowseResultsRenderer?.tabs?.[0]?.tabRenderer?.content
          ?.sectionListRenderer?.contents?.[0]?.itemSectionRenderer?.contents?.[0]
          ?.playlistVideoListRenderer?.contents || [];
      const title =
        data?.header?.playlistHeaderRenderer?.title?.runs?.[0]?.text || 'Playlist YouTube';
      const tracksFallback = contents
        .filter(item => item.playlistVideoRenderer)
        .map(item => {
          const v = item.playlistVideoRenderer;
          const id = v.videoId;
          const trackTitle = v.title?.runs?.[0]?.text || '';
          const channel = v.shortBylineText?.runs?.[0]?.text || '';
          const thumb = `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
          return { id, title: trackTitle, channel, thumb };
        })
        .filter(t => t.id && t.title);
      if (!tracksFallback.length) throw new Error('Playlist kosong atau tidak bisa diakses');
      return NextResponse.json(
        { title, tracks: tracksFallback },
        { headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate' } }
      );
    } catch {
      return NextResponse.json({ error: e.message }, { status: 500 });
    }
  }
}
