INSERT OR IGNORE INTO exercises(name, category, equipment, difficulty, duration_minutes, instructions) VALUES
('Squat', 'Lower body', 'bodyweight, dumbbells', 'beginner', 12, 'Sit hips back, keep knees tracking over toes, and stand tall.'),
('Bicep curl', 'Upper body', 'dumbbells', 'beginner', 8, 'Keep elbows close to your sides and lower the weights with control.'),
('Arm circles', 'Mobility', 'bodyweight', 'beginner', 5, 'Make small controlled circles, then gradually increase their size.'),
('Glute bridge', 'Lower body', 'bodyweight', 'beginner', 8, 'Press through your feet and lift hips without arching the lower back.'),
('Incline push-up', 'Upper body', 'bodyweight', 'beginner', 10, 'Keep your body in a straight line and lower your chest toward a stable surface.'),
('Dead bug', 'Core', 'bodyweight', 'beginner', 8, 'Keep your lower back gently grounded as opposite arm and leg extend.');

INSERT OR IGNORE INTO recipes(name, calories, protein_g, cost, dietary_tags, ingredients) VALUES
('Greek yogurt berry bowl', 360, 28, 3.20, 'high protein, vegetarian', 'Greek yogurt, mixed berries, oats, chia seeds'),
('Chicken rice power bowl', 520, 42, 4.80, 'high protein, dairy free', 'Chicken breast, brown rice, spinach, cucumber, lemon'),
('Peanut tofu stir-fry', 490, 25, 3.60, 'vegetarian, dairy free', 'Tofu, broccoli, brown rice, peanut sauce'),
('Egg and avocado toast', 410, 22, 2.90, 'vegetarian', 'Eggs, wholegrain bread, avocado, tomato'),
('Lentil tomato soup', 430, 24, 2.40, 'vegan, dairy free, budget', 'Lentils, tomatoes, carrots, onion, vegetable stock');

-- Extra catalog options are inserted without changing existing records.
INSERT OR IGNORE INTO exercises(name,category,equipment,difficulty,duration_minutes,instructions) VALUES
('Walking','Cardio','bodyweight','beginner',10,'Walk at a comfortable conversational pace.'),
('Standing calf raise','Lower body','bodyweight','beginner',5,'Hold a stable support and raise your heels slowly.');
INSERT OR IGNORE INTO recipes(name,calories,protein_g,cost,dietary_tags,ingredients) VALUES
('Chickpea rice bowl',460,19,2.10,'vegan, vegetarian, dairy free, gluten free, nut free','Chickpeas, rice, carrots, spinach, olive oil'),
('Oat banana bowl',380,12,1.40,'vegan, vegetarian, dairy free, nut free','Certified gluten-free oats, banana, water, chia seeds');
