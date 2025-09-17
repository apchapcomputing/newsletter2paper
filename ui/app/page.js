'use client'

import { useState, useEffect } from 'react';
import Image from "next/image";

export default function Home() {
  const [publications, setPublications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPublications = async () => {
      try {
        const response = await fetch('/api/publications');
        if (!response.ok) {
          throw new Error('Failed to fetch publications');
        }
        const data = await response.json();
        console.log('Fetched publications:', data);

        // get rss url for each publication url and save to state
        const publicationsWithRss = await Promise.all(data.publications.map(async (p) => {
          const rssUrl = await getRssFeedUrl(p.url);
          return { ...p, feed_url: rssUrl };
        }));
        setPublications(publicationsWithRss);
      } catch (err) {
        console.error('Error fetching publications:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPublications();
  }, []);

  const getRssFeedUrl = async (url) => {
    try {
      const response = await fetch(`/api/rss/url?webpage_url=${encodeURIComponent(url)}`);
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      const data = await response.json();
      return data.feed_url;
    } catch (error) {
      console.error("Failed to fetch RSS feed URL:", error);
    }
  }

  return (
    <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
        <h1 className="text-4xl font-bold text-center sm:text-left">Your Newspaper</h1>
        
        {/* Generate Buttons */}
        <div className="flex flex-row gap-4 text-center sm:text-left align-center">
          <button className="bg-orange-400 p-2 rounded">Now</button>
          <button className="bg-orange-400 p-2 rounded">Weekly</button>
          <button className="bg-orange-400 p-2 rounded" onClick={() => getRssFeedUrl("http://kyla.substack.com")}>Get RSS Feed URL</button>
        </div>
        
        {/* List of Active Substacks to Print */}
        <div className="flex flex-col gap-4">
          <h2 className="text-2xl font-semibold">Substacks to Print</h2>
          {loading ? (
            <p>Loading publications...</p>
          ) : error ? (
            <p className="text-red-500">Error: {error}</p>
          ) : (
            <ul className="list-disc list-inside">
              {publications.map((publication, index) => (
                <li key={index}>
                  <a
                    href={publication.feed_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    {publication.title}
                  </a>
                  {publication.publisher && (
                    <span className="text-gray-500 ml-2">({publication.publisher})</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
      <footer className="row-start-3 flex gap-[24px] flex-wrap items-center justify-center">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org/learn?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/file.svg"
            alt="File icon"
            width={16}
            height={16}
          />
          Learn
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://vercel.com/templates?framework=next.js&utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/window.svg"
            alt="Window icon"
            width={16}
            height={16}
          />
          Examples
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/globe.svg"
            alt="Globe icon"
            width={16}
            height={16}
          />
          Go to nextjs.org →
        </a>
      </footer>
    </div>
  );
}
