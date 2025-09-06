import fs from "fs";
import path from "path";

import Image from "next/image";


export default function Home() {

  // Read the publications.txt file
  const filePath = path.join(process.cwd(), "publications.csv");
  const fileContents = fs.readFileSync(filePath, "utf-8");

  // Parse the CSV file into an array of objects
  const publications = fileContents
    .split("\n")
    .filter(Boolean) // Remove empty lines
    .map((line) => {
      const [rssLink, title] = line.split(","); // Split by comma
      return { rssLink: rssLink.trim(), title: title.trim() }; // Trim whitespace
    });

  return (
    <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start">
        <h1 className="text-4xl font-bold text-center sm:text-left">Your Newspaper</h1>
        
        {/* Generate Buttons */}
        <div className="flex flex-row gap-4 text-center sm:text-left align-center">
          <button className="bg-orange-400 p-2 rounded">Now</button>
          <button className="bg-orange-400 p-2 rounded">Weekly</button>
        </div>
        
        {/* List of Active Substacks to Print */}
        <div className="flex flex-col gap-4">
          <h2 className="text-2xl font-semibold">Substacks to Print</h2>
          <ul className="list-disc list-inside">
            {publications.map((publication, index) => (
              <li key={index}>
                <a
                  href={publication.rssLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline"
                >
                  {publication.title}
                </a>
              </li>
            ))}
          </ul>
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
