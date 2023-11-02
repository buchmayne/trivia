-- 'Single Slide Multiple Choice No Answer Bank'
-- 'Single Slide Multiple Choice With Answer Bank'
-- 'Multi Slide With Answer Bank'
-- 'Multi Slide No Answer Bank'
-- 'Single Slide Open Ended'
-- 'Single Slide Media'

drop table if exists questions;
drop table if exists single_slide_multiple_choice_no_answer_bank;
drop table if exists choices_single_slide_multiple_choice_no_answer_bank;

create table questions (
	id SERIAL primary key,
	title varchar,
	question_type varchar,
	category varchar,
	game_id varchar default '052023',
	has_been_used bool default true,
	question_number integer

);

insert into questions (question_type, title, question_number, category)
values 
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following sports franchises, name a city that the franchise was previoulsy located in (1 Point Each)', 1, 'Sports Franchises'),
	('Single Slide Open Ended', 'Can you name all of the current Supreme Court justices (1 Point for Each Correct Answer, -1 Point for Each Incorrect Answer)', 2, 'Justice'),
	('Single Slide Multiple Choice No Answer Bank', 'Identify the punctuation mark that shares a key on a computer keyboard with each of the following numbers (1 Point Each)', 3, 'Computers'),
	('Single Slide Multiple Choice With Answer Bank', 'Match the coffee drink to the description (1 Point Each)', 4, 'Coffee'),
	('Single Slide Multiple Choice No Answer Bank', 'Identify what has a greater land area (1 Point Each)', 5, 'Land'),
	('Single Slide Multiple Choice With Answer Bank', 'Match the dying words of the famous person to the famous person (1 Point Each)', 6, 'Words'),
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following pairs of historical figures, were they alive at the same time? (1 Point Each)', 7, 'Lifetimes'),
	('Single Slide Multiple Choice With Answer Bank', 'Match each of the following phobias to the description of the phobia (1 Point Each)', 8, 'Fear'),
	('Multi Slide With Answer Bank', 'You will be shown a picture of a city from each of the following regions: Central America, The Middle East, Central Asia (The Stans), Sub-Saharan Africa. Each city shown is the city with the largest population of any city in that region. For 1 point, match the picture of a city to the region. For 2 points, name the country for which the city is located. For 3 points, name the city shown in the image. (24 Points Possible)', 9, 'Cities'),
	('Single Slide Multiple Choice No Answer Bank', 'For each of the following unlabeled countries, you will be given the population in a specific year, and the average annual population growth rate between that year and a later year. Estimate the population in the outer year (2 Point Each)', 10, 'Growth'),
	('Single Slide Multiple Choice No Answer Bank', 'Rank the following companies, from highest to lowest 2022 revenues. (1 Point Each)', 11, 'Business'),
	('Single Slide Multiple Choice No Answer Bank', 'Rank the following companies, from highest to lowest 2022 revenues. (1 Point Each)', 12, 'Business'),
	('Single Slide Multiple Choice No Answer Bank', 'Based on the clue identify the person/character/thing/etc. The last name in the answer for question A will be the first name in the answer for question B, and so on. (2 Points Each)', 13, 'First Name Last Name'),
	('Multi Slide No Answer Bank', 'You will be shown the poster for four films. For each of these films, the director of the film also directed a film that won the Oscar for Best Picture between 2010-2023. Name the film that won Best Picture for 2 Points, and name the director for 3 points (5 Points Each).', 14, 'Movies'),
	('Single Slide Media', 'Identify the Studio/Production company by their iconic sound (2 Points Each).', 15, 'Movies'),
	('Single Slide Media', 'Identify the data being shown on the map (5 Points)', 16, 'Guess The Data'),
	('Single Slide Media', 'Identify the place from the aerial photograph (5 Points)', 17, 'Birds Eye View'),
	('Single Slide Media', 'Each of the four images is a visual punn. All four of the images represent something that belong to the same category. Identify each image and the category (2 Points per image, 2 Points for the category, 10 Points total). For this trivia there is an added element to the puzzle. Step 1 in solving the puzzle is deciphering what the image is. Step 2 requires using the example provided, to figure out the relationship between the clue and the answer, and then apply that relationship to each of the images in step 1.', 18, 'Visual Pun')
;


create table single_slide_multiple_choice_no_answer_bank as (
	select
		id,
		title,
		category,
		game_id,
		has_been_used,
		question_number,
		question_type
	from 
		questions
	where question_type = 'Single Slide Multiple Choice No Answer Bank'
);

alter table single_slide_multiple_choice_no_answer_bank
add column points integer,
add column points_application varchar default 'Each',
add column n_options integer;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 1;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 3;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 5;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 7;

update single_slide_multiple_choice_no_answer_bank
	set points = 2, n_options = 2
	where question_number = 10;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 11;

update single_slide_multiple_choice_no_answer_bank
	set points = 1, n_options = 4
	where question_number = 12;

update single_slide_multiple_choice_no_answer_bank
	set points = 2, n_options = 4
	where question_number = 13;
				


create table choices_single_slide_multiple_choice_no_answer_bank as (
	select 
		ssmcnab.id,
		ssmcnab.title,
		ssmcnab.category,
		ssmcnab.game_id,
		ssmcnab.question_number,
		ssmcnab.points,
		ssmcnab.points_application,
		ssmcnab.n_options,
		case 
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 1 then 'A'
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 2 then 'B'
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 3 then 'C'
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 4 then 'D'
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 5 then 'E'
			when row_number() over (partition by ssmcnab.id order by ssmcnab.question_number) = 6 then 'F'
			else 'UNKNOWN'
		end as choice_id
	from single_slide_multiple_choice_no_answer_bank ssmcnab
	join generate_series(1, ssmcnab.n_options) on true
);


alter table choices_single_slide_multiple_choice_no_answer_bank
add column choice_text varchar,
add column choice_answer varchar;

-- Question 1
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Arizona Cardinals', choice_answer = 'Chicago, St. Louis'
	where question_number = 1 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Sacramento Kings', choice_answer = 'Kansas City'
	where question_number = 1 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Washington Nationals', choice_answer = 'Montreal'
	where question_number = 1 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Oakland Athletics', choice_answer = 'Kansas City'
	where question_number = 1 and choice_id = 'D';

-- Question 3
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '1', choice_answer = '!'
	where question_number = 3 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '3', choice_answer = '#'
	where question_number = 3 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '6', choice_answer = '^'
	where question_number = 3 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '9', choice_answer = '('
	where question_number = 3 and choice_id = 'D';

-- Question 5
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '(Oregon + California) or France', choice_answer = '262,000 mi2 > 213,000 mi2'
	where question_number = 5 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '(Germany + Poland + Czech Republic) or Texas', choice_answer = '289,000 mi2 > 268,000 mi2'
	where question_number = 5 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '(USA + Canada) or Russia', choice_answer = '7.65 million mi2 > 6.6 million mi2'
	where question_number = 5 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = '(New York (State) + New Jersey + Pennsylvania) or United Kingdom', choice_answer = '109,000 mi2 > 93,000 mi2'
	where question_number = 5 and choice_id = 'D';

-- Question 7
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Martin Luther King Jr. & Mark Twain', choice_answer = 'False (Born: 1929, Died: 1910)'
	where question_number = 7 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Mahatma Gandhi & Karl Marx', choice_answer = 'True (Born: 1869, Died: 1883)'
	where question_number = 7 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'George Washington & Abraham Lincoln', choice_answer = 'False (Died: 1799, Born: 1809)'
	where question_number = 7 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Billie Eilish & Ronald Reagan', choice_answer = 'True (Born: 2001, Died: 2004)'
	where question_number = 7 and choice_id = 'D';

-- Question 10
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Population in 1980 is 226.5 million, what is the population in 2020? The average annual population growth rate is 1.13%', choice_answer = '329.5 (313.025, 345.975) Accepted'
	where question_number = 10 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Population in 1960 is 36.27 million, what is the population in 1970? The average annual population growth rate is 3.86%', choice_answer = '50.29 (47.7755, 52.8045) Accepted'
	where question_number = 10 and choice_id = 'B';

-- Question 11
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Coca-Cola Company', choice_answer = '4th - 38,655 Million'
	where question_number = 11 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'CVS Health', choice_answer = '1st - 292,111 Million'
	where question_number = 11 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Microsoft', choice_answer = '2nd - 198,087 Million'
	where question_number = 11 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'PepsiCo', choice_answer = '3rd - 79,474 Million'
	where question_number = 11 and choice_id = 'D';

-- Question 12
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Nike', choice_answer = '4th - 73k'
	where question_number = 12 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Tesla', choice_answer = '3rd - 99k'
	where question_number = 12 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'The Walt Disney Company', choice_answer = '2nd - 171k'
	where question_number = 12 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Wells Fargo', choice_answer = '1st - 247k'
	where question_number = 12 and choice_id = 'D';

-- Question 13
update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'A fictional monkey who is the title character of a series of popular childrens books.', choice_answer = 'Curious George'
	where question_number = 13 and choice_id = 'A';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Iconic british pop star of the 1980s and 1990s. A hit song of theirs contains the lyric "Guilty feet have got no rhythm", and another hit song of theirs was covered by Limp Bizkit on their debut album.', choice_answer = 'George Michael'
	where question_number = 13 and choice_id = 'B';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'This actor was in HBOs crime drama The Wire early in his career, before going on to bigger roles, including a part in the Marvel Cinematic Universe. He made his directoral debut in 2023.', choice_answer = 'Michael B. Jordan'
	where question_number = 13 and choice_id = 'C';

update choices_single_slide_multiple_choice_no_answer_bank
	set choice_text = 'Very likely the most famous Canadian Psychologist, dead or alive. Most people know him as a podcaster who discusses cultural issues', choice_answer = 'Jordan Peterson'
	where question_number = 13 and choice_id = 'D';


select * from choices_single_slide_multiple_choice_no_answer_bank ssmcnab ;

