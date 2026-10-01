-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create publications table
CREATE TABLE publications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    rss_feed_url VARCHAR(512) NOT NULL,
    publisher VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create issues table
CREATE TABLE issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    format VARCHAR(50) NOT NULL,
    target_email VARCHAR(255),
    frequency VARCHAR(50) NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create articles table
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),
    date_published TIMESTAMP WITH TIME ZONE NOT NULL,
    author VARCHAR(255) NOT NULL,
    publication_id UUID REFERENCES publications(id),
    content_url VARCHAR(512) NOT NULL,
    storage_url VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_issues junction table
CREATE TABLE user_issues (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    issue_id UUID REFERENCES issues(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, issue_id)
);

-- Create issue_publications junction table
CREATE TABLE issue_publications (
    issue_id UUID REFERENCES issues(id) ON DELETE CASCADE,
    publication_id UUID REFERENCES publications(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (issue_id, publication_id)
);

-- Create indexes for better performance
CREATE INDEX idx_publications_title ON publications(title);
CREATE INDEX idx_articles_publication_id ON articles(publication_id);
CREATE INDEX idx_articles_date_published ON articles(date_published);
CREATE INDEX idx_user_issues_user_id ON user_issues(user_id);
CREATE INDEX idx_user_issues_issue_id ON user_issues(issue_id);
CREATE INDEX idx_issue_publications_issue_id ON issue_publications(issue_id);
CREATE INDEX idx_issue_publications_publication_id ON issue_publications(publication_id);

-- Add some sample data
INSERT INTO users (email, username, password, first_name, last_name) VALUES
    ('john.doe@example.com', 'johndoe', 'hashed_password_1', 'John', 'Doe'),
    ('sarah.smith@example.com', 'sarahs', 'hashed_password_2', 'Sarah', 'Smith'),
    ('michael.johnson@example.com', 'michaelj', 'hashed_password_3', 'Michael', 'Johnson'),
    ('emma.wilson@example.com', 'emmaw', 'hashed_password_4', 'Emma', 'Wilson'),
    ('james.brown@example.com', 'jamesb', 'hashed_password_5', 'James', 'Brown');

-- Insert sample publications (based on what was in your original publications.csv)
INSERT INTO publications (title, url, rss_feed_url, publisher) VALUES
    ('Kyla''s Newsletter', 'https://kyla.substack.com', 'https://kyla.substack.com/feed', 'Kyla Scanlon'),
    ('The Elysian', 'https://www.elysian.press', 'https://www.elysian.press/feed', 'Elle Griffin'),
    ('Ultra Successful', 'https://drgurner.substack.com', 'https://drgurner.substack.com/feed', 'Dr. Julie Gurner'),
    ('Tech Insights Weekly', 'https://techinsights.substack.com', 'https://techinsights.substack.com/feed', 'Sarah Chen'),
    ('Future of Work Digest', 'https://futureofwork.substack.com', 'https://futureofwork.substack.com/feed', 'Mark Thompson');

-- Insert sample issues
INSERT INTO issues (format, target_email, frequency, title) VALUES
    ('newspaper', 'john.doe@example.com', 'daily', 'Daily Tech Digest'),
    ('essay', 'sarah.smith@example.com', 'weekly', 'Weekly Publishing Insights'),
    ('newspaper', 'michael.johnson@example.com', 'weekly', 'Leadership Weekly'),
    ('essay', 'emma.wilson@example.com', 'monthly', 'Monthly Tech Roundup'),
    ('newspaper', 'james.brown@example.com', 'daily', 'Future Work Daily');

-- Insert sample articles
INSERT INTO articles (title, subtitle, date_published, author, publication_id, content_url, storage_url) VALUES
    ('Market Analysis Q3 2025', 'Understanding Market Trends', '2025-09-20T10:00:00Z', 'Kyla Scanlon', 
     (SELECT id FROM publications WHERE title = 'Kyla''s Newsletter'), 
     'https://kyla.substack.com/p/market-q3-2025', 
     'https://storage.example.com/articles/market-q3-2025'),
    ('The Future of Digital Publishing', 'New Horizons', '2025-09-18T14:30:00Z', 'Elle Griffin', 
     (SELECT id FROM publications WHERE title = 'The Elysian'), 
     'https://elysian.press/p/future-publishing', 
     'https://storage.example.com/articles/future-publishing'),
    ('Leadership in Crisis Times', 'Managing Uncertainty', '2025-09-15T09:15:00Z', 'Dr. Julie Gurner', 
     (SELECT id FROM publications WHERE title = 'Ultra Successful'), 
     'https://drgurner.substack.com/p/leadership-crisis', 
     'https://storage.example.com/articles/leadership-crisis'),
    ('AI Revolution 2025', 'The Next Wave', '2025-09-22T16:45:00Z', 'Sarah Chen', 
     (SELECT id FROM publications WHERE title = 'Tech Insights Weekly'), 
     'https://techinsights.substack.com/p/ai-revolution', 
     'https://storage.example.com/articles/ai-revolution'),
    ('Remote Work Trends', 'The Future of Work', '2025-09-21T11:20:00Z', 'Mark Thompson', 
     (SELECT id FROM publications WHERE title = 'Future of Work Digest'), 
     'https://futureofwork.substack.com/p/remote-work', 
     'https://storage.example.com/articles/remote-work');

-- Create relationships between users and issues
INSERT INTO user_issues (user_id, issue_id) VALUES
    ((SELECT id FROM users WHERE email = 'john.doe@example.com'), 
     (SELECT id FROM issues WHERE target_email = 'john.doe@example.com')),
    ((SELECT id FROM users WHERE email = 'sarah.smith@example.com'), 
     (SELECT id FROM issues WHERE target_email = 'sarah.smith@example.com')),
    ((SELECT id FROM users WHERE email = 'michael.johnson@example.com'), 
     (SELECT id FROM issues WHERE target_email = 'michael.johnson@example.com')),
    ((SELECT id FROM users WHERE email = 'emma.wilson@example.com'), 
     (SELECT id FROM issues WHERE target_email = 'emma.wilson@example.com')),
    ((SELECT id FROM users WHERE email = 'james.brown@example.com'), 
     (SELECT id FROM issues WHERE target_email = 'james.brown@example.com'));

-- Create relationships between issues and publications
INSERT INTO issue_publications (issue_id, publication_id) VALUES
    ((SELECT id FROM issues WHERE target_email = 'john.doe@example.com'), 
     (SELECT id FROM publications WHERE title = 'Tech Insights Weekly')),
    ((SELECT id FROM issues WHERE target_email = 'sarah.smith@example.com'), 
     (SELECT id FROM publications WHERE title = 'The Elysian')),
    ((SELECT id FROM issues WHERE target_email = 'michael.johnson@example.com'), 
     (SELECT id FROM publications WHERE title = 'Ultra Successful')),
    ((SELECT id FROM issues WHERE target_email = 'emma.wilson@example.com'), 
     (SELECT id FROM publications WHERE title = 'Tech Insights Weekly')),
    ((SELECT id FROM issues WHERE target_email = 'james.brown@example.com'), 
     (SELECT id FROM publications WHERE title = 'Future of Work Digest'));